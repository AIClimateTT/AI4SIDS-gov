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

PLACEHOLDER_RE = re.compile(r"^\{(\w+)\}$")


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


def assemble_fact_table(template: Template, params: dict, session: Session, request_id: str) -> FactTable:
    validate_params(template, params)
    all_facts: list[Fact] = []
    gaps: list[str] = []

    for requirement in template.data_requirements:
        module = get_module(requirement.module)
        if module is None:
            raise ValueError(f"unknown data module: {requirement.module}")
        resolved = resolve_params(requirement.params, params)
        facts = module.run_metric(requirement.metric, resolved, session)
        if not facts:
            gaps.append(f"No data returned for {requirement.module}.{requirement.metric} with params {resolved}")
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
    fact_table: FactTable
    narrative: str
    status: Literal["ok", "needs_review"]
    violations: list[CitationViolation]
    markdown: str


def build_retry_content(user_content: str, violations: list[CitationViolation]) -> str:
    violation_lines = "\n".join(f"- {v.kind}: {v.detail} (sentence: {v.sentence!r})" for v in violations)
    return (
        f"{user_content}\n\n"
        f"Your previous narrative had citation violations. Fix them and regenerate:\n{violation_lines}"
    )


def generate_report(template: Template, params: dict, session: Session, llm_client: LLMClient) -> GeneratedReport:
    request_id = str(uuid.uuid4())
    fact_table = assemble_fact_table(template, params, session, request_id)

    user_content = fact_table.model_dump_json()
    narrative = llm_client.generate(template.narration.system_prompt, user_content)
    result = check_citations(narrative, fact_table)

    if not result.passed:
        retry_content = build_retry_content(user_content, result.violations)
        narrative = llm_client.generate(template.narration.system_prompt, retry_content)
        result = check_citations(narrative, fact_table)

    status: Literal["ok", "needs_review"] = "ok" if result.passed else "needs_review"
    markdown = render_report(template, fact_table, narrative)

    return GeneratedReport(
        request_id=request_id,
        template=template.name,
        template_version=template.version,
        params=params,
        fact_table=fact_table,
        narrative=narrative,
        status=status,
        violations=result.violations,
        markdown=markdown,
    )
