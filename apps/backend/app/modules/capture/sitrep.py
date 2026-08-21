from datetime import datetime, timezone

from app.core.contracts import Fact, FactTable, Template
from app.core.engine import GeneratedReport, narrate_fact_table
from app.core.llm import LLMClient
from app.modules.capture.facts import assemble_working_set_facts
from app.modules.capture.schemas import CaptureLog, CaptureWorkingSet


def sitrep_preamble(
    *,
    event_title: str,
    alert_level: str,
    as_at: datetime,
    situation_overview: str | None,
    present_activity: str | None,
    logs: list[CaptureLog],
) -> str:
    parts = [
        f"**Event:** {event_title}",
        f"**Alert:** {alert_level}",
        f"**As at:** {as_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    if situation_overview:
        parts.extend(["", situation_overview])
    if present_activity:
        parts.extend(["", f"Present activity: {present_activity}"])
    statements = [log.statement for log in logs if log.statement]
    if statements:
        parts.extend(["", "## Situation logs", ""])
        parts.extend(f"- {statement}" for statement in statements)
    return "\n".join(parts)


def generate_working_set_sitrep(
    working: CaptureWorkingSet,
    *,
    corporation: str,
    event_id: int | None,
    event_title: str,
    template: Template,
    llm_client: LLMClient,
    request_id: str,
) -> GeneratedReport:
    facts = assemble_working_set_facts(
        working, corporation=corporation, event_id=event_id
    )
    gaps: list[str] = []
    for fact in facts:
        for gap in fact.gaps:
            if gap not in gaps:
                gaps.append(gap)
    renumbered: list[Fact] = []
    for index, fact in enumerate(facts, start=1):
        new_citation = fact.citation.model_copy(update={"cid": f"C{index:03d}"})
        renumbered.append(fact.model_copy(update={"citation": new_citation}))
    params = {"corporation": corporation}
    fact_table = FactTable(
        request_id=request_id,
        template=template.name,
        template_version=template.version,
        params=params,
        generated_at=datetime.now(timezone.utc),
        facts=renumbered,
        gaps=gaps,
    )
    generated = narrate_fact_table(
        template, fact_table, llm_client, template.data_requirements
    )
    as_at = working.as_at or datetime.now(timezone.utc)
    preamble = sitrep_preamble(
        event_title=event_title,
        alert_level=working.alert_level,
        as_at=as_at,
        situation_overview=working.situation_overview,
        present_activity=working.present_activity,
        logs=working.logs,
    )
    markdown = generated.markdown.replace(
        f"# {template.title}\n\n",
        f"# {template.title}\n\n{preamble}\n\n",
        1,
    )
    return generated.model_copy(update={"markdown": markdown, "params": params})
