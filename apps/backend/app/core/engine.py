import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.contracts import DataRequirement, Fact, FactTable, Template
from app.core.registry import get_module

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
        params=params,
        generated_at=datetime.now(timezone.utc),
        facts=renumbered,
        gaps=gaps,
    )
