import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.citation_check import CitationViolation, check_citations
from app.core.contracts import DataRequirement, Fact, FactTable, Template
from app.core.llm import LLMClient
from app.core.registry import get_module
from app.core.renderer import render_report
from app.quality.contracts import QualityEval
from app.quality.score import score_quality

PLACEHOLDER_RE = re.compile(r"^\{(\w+)\}$")

CITATION_RULES = """RULES (absolute — always apply):
- Use ONLY numbers present in the fact table you are given as JSON. Never compute, sum, estimate, or round a number that is not already present.
- Every sentence containing a figure must end with its citation marker, e.g. [C001]. Citation markers look like C001, C002, etc.
- Never break a line between a figure and its citation marker. Each list item and each table row carries its own marker — the checker reads a line at a time.
- Distinguish validated vs pending figures exactly as labeled in the fact table's "verification" field.
- If the fact table lists gaps, state them plainly in a Data Gaps section.
- Write every figure as digits, never words — "15", not "fifteen"."""


def compose_system_prompt(template: Template) -> str:
    identity = template.narration.identity.strip()
    compose = template.narration.skills.compose.strip()
    body = "\n\n".join(part for part in (identity, compose) if part)
    return f"{CITATION_RULES}\n\n{body}" if body else CITATION_RULES


def resolve_params(raw_params: dict, template_params: dict) -> dict:
    resolved = {}
    for key, value in raw_params.items():
        if isinstance(value, str):
            match = PLACEHOLDER_RE.match(value)
            if match:
                resolved[key] = template_params.get(match.group(1))
                continue
        resolved[key] = value
    return resolved


def validate_params(template: Template, params: dict) -> None:
    missing = [p.name for p in template.params if p.required and params.get(p.name) is None]
    if missing:
        raise ValueError(f"missing required params for template {template.name!r}: {missing}")


def resolve_effective_requirements(
    template: Template,
    data_requirements: list[DataRequirement] | None,
) -> list[DataRequirement]:
    effective = data_requirements if data_requirements is not None else template.data_requirements
    if not effective:
        raise ValueError("at least one data requirement is required to generate a report")
    return effective


def assemble_fact_table(
    template: Template,
    params: dict,
    session: Session,
    request_id: str,
    requirements: list[DataRequirement],
) -> FactTable:
    validate_params(template, params)
    all_facts: list[Fact] = []
    gaps: list[str] = []

    for requirement in requirements:
        module = get_module(requirement.module)
        if module is None:
            raise ValueError(f"unknown data module: {requirement.module}")
        resolved = resolve_params(requirement.params, params)
        facts = module.run_metric(requirement.metric, resolved, session)
        if not facts:
            gaps.append(f"No data returned for {requirement.module}.{requirement.metric} with params {resolved}")
        # A metric knows things about its own rows that the caller cannot see
        # — chiefly rows its selection predicate silently drops. Hoisted here
        # because FactTable.gaps is what the narration prompt points the model
        # at, and what the renderer prints as "Data Gaps". Deduped, order
        # preserved: two metrics over the same rows report the same caveat.
        for fact in facts:
            for gap in fact.gaps:
                if gap not in gaps:
                    gaps.append(gap)
        all_facts.extend(facts)

    renumbered: list[Fact] = []
    for index, fact in enumerate(all_facts, start=1):
        new_citation = fact.citation.model_copy(update={"cid": f"C{index:03d}"})
        renumbered.append(fact.model_copy(update={"citation": new_citation}))

    return FactTable(
        request_id=request_id,
        template=template.name,
        template_version=template.version,
        params=params,
        generated_at=datetime.now(timezone.utc),
        facts=renumbered,
        gaps=gaps,
    )


class GeneratedReport(BaseModel):
    request_id: str
    template: str
    template_version: int = 1
    params: dict
    data_requirements: list[DataRequirement]
    fact_table: FactTable
    narrative: str
    status: Literal["ok", "needs_review"]
    violations: list[CitationViolation]
    markdown: str
    # The same facts rendered for issue: no citation markers, no appendix.
    # Produced here rather than by a consumer so the draft and the issued
    # document can never come from two different renderers.
    final_markdown: str = ""
    quality_eval: QualityEval | None = None


def _fact_table_for_llm(fact_table: FactTable) -> FactTable:
    # The LLM narrates from fact values and cites by cid; it never reads
    # record_ids. Left in, those ids run into hundreds of KB at realistic
    # data volumes (thousands of rows per metric, multiple metrics per
    # template) and blow straight through settings.ollama_num_ctx — an
    # overflowed context silently returns an empty narrative, resurrecting a
    # failure mode this codebase already fixed once. Storage and the
    # citation appendix use the full fact_table; only the LLM-facing copy
    # is pared down, and no cap is reintroduced anywhere else.
    # Per-fact gaps go too: assemble_fact_table has already hoisted them into
    # fact_table.gaps, which is where the prompt tells the model to look.
    # Leaving both would show the model the same caveat twice.
    pared_facts = [
        fact.model_copy(
            update={
                "citation": fact.citation.model_copy(update={"record_ids": None}),
                "gaps": [],
            }
        )
        for fact in fact_table.facts
    ]
    return fact_table.model_copy(update={"facts": pared_facts})


def build_retry_content(user_content: str, violations: list[CitationViolation]) -> str:
    violation_lines = "\n".join(f"- {v.kind}: {v.detail} (sentence: {v.sentence!r})" for v in violations)
    return (
        f"{user_content}\n\n"
        f"Your previous narrative had citation violations. Fix them and regenerate:\n{violation_lines}"
    )


def generate_report(
    template: Template,
    params: dict,
    session: Session,
    llm_client: LLMClient,
    data_requirements: list[DataRequirement] | None = None,
    request_id: str | None = None,
) -> GeneratedReport:
    request_id = request_id or str(uuid.uuid4())
    effective_requirements = resolve_effective_requirements(template, data_requirements)
    fact_table = assemble_fact_table(template, params, session, request_id, effective_requirements)
    return narrate_fact_table(template, fact_table, llm_client, effective_requirements)


def narrate_fact_table(
    template: Template,
    fact_table: FactTable,
    llm_client: LLMClient,
    data_requirements: list[DataRequirement] | None = None,
) -> GeneratedReport:
    system_prompt = compose_system_prompt(template)
    user_content = _fact_table_for_llm(fact_table).model_dump_json()
    narrative = llm_client.generate(system_prompt, user_content)
    result = check_citations(narrative, fact_table)

    if not result.passed:
        retry_content = build_retry_content(user_content, result.violations)
        narrative = llm_client.generate(system_prompt, retry_content)
        result = check_citations(narrative, fact_table)

    status: Literal["ok", "needs_review"] = "ok" if result.passed else "needs_review"
    markdown = render_report(template, fact_table, narrative)
    final_markdown = render_report(
        template, fact_table, narrative, include_citations=False
    )
    quality_eval = score_quality(template, fact_table, narrative, markdown, result)

    return GeneratedReport(
        request_id=fact_table.request_id,
        template=template.name,
        template_version=template.version,
        params=fact_table.params,
        data_requirements=data_requirements or [],
        fact_table=fact_table,
        narrative=narrative,
        status=status,
        violations=result.violations,
        markdown=markdown,
        final_markdown=final_markdown,
        quality_eval=quality_eval,
    )
