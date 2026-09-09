from datetime import datetime, timezone
import re

from sqlalchemy.orm import Session

from app.core.contracts import Fact, FactTable, Template
from app.core.engine import GeneratedReport, narrate_fact_table
from app.core.llm import LLMClient
from app.modules.capture.facts import assemble_working_set_facts
from app.modules.capture.missing import missing_fields
from app.modules.capture.models import CaptureSession
from app.modules.capture.schemas import CaptureWorkingSet


def sitrep_preamble(
    *,
    event_title: str,
    alert_level: str,
    as_at: datetime,
    situation_overview: str | None,
    present_activity: str | None,
) -> str:
    # Two trailing spaces are a markdown hard break. Without them these three
    # fields collapse into one run-on paragraph instead of a filing header.
    fields = [
        f"**Event:** {event_title}",
        f"**Alert:** {alert_level.replace('_', ' ').strip().title()}",
        f"**As at:** {as_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    # Separate paragraphs: a single newline collapses in markdown, which is
    # what put Event / Alert / As at on one unreadable line.
    parts = ["\n\n".join(fields)]
    if situation_overview:
        parts.extend(["", situation_overview])
    if present_activity:
        parts.extend(["", f"Present activity: {present_activity}"])
    return "\n".join(parts)


def _location_gaps(working: CaptureWorkingSet) -> list[str]:
    gaps: list[str] = []
    for incident in working.incidents:
        label = incident.row_id or incident.incident_summary or "incident"
        if not incident.community and not incident.street:
            gaps.append(f"Incident {label}: community and street not recorded")
        elif not incident.community:
            gaps.append(f"Incident {label}: community not recorded")
        elif not incident.street:
            gaps.append(f"Incident {label}: street not recorded")
    for field in missing_fields(working):
        if field.message not in gaps:
            gaps.append(field.message)
    return gaps


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
    for gap in _location_gaps(working):
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
    # The draft pane already shows cited facts in a table. The issued
    # document is the prose (plus filing tables); do not reprint the
    # same facts as a citation appendix, even if a stored template still
    # asks for one.
    template = template.model_copy(
        update={
            "render": template.render.model_copy(
                update={"include_citation_appendix": False}
            )
        }
    )
    generated = narrate_fact_table(
        template, fact_table, llm_client, template.data_requirements
    )
    generated = attach_sitrep_preamble(
        generated, working, event_title=event_title, template=template
    )
    return generated.model_copy(update={"params": params})


def attach_sitrep_preamble(
    generated: GeneratedReport,
    working: CaptureWorkingSet,
    *,
    event_title: str,
    template: Template,
) -> GeneratedReport:
    as_at = working.as_at or datetime.now(timezone.utc)
    preamble = sitrep_preamble(
        event_title=event_title,
        alert_level=working.alert_level,
        as_at=as_at,
        situation_overview=working.situation_overview,
        present_activity=working.present_activity,
    )
    def with_preamble(markdown: str) -> str:
        updated, count = re.subn(
            r"(^# [^\n]+\n\n)",
            rf"\1{preamble}\n\n",
            markdown,
            count=1,
        )
        if count:
            return updated
        return markdown.replace(
            f"# {template.title}\n\n",
            f"# {template.title}\n\n{preamble}\n\n",
            1,
        )

    return generated.model_copy(
        update={
            "markdown": with_preamble(generated.markdown),
            "final_markdown": with_preamble(generated.final_markdown),
        }
    )


def _naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def sitrep_is_stale(row: CaptureSession) -> bool:
    if not row.sitrep_markdown or row.sitrep_source_updated_at is None:
        return True
    return row.sitrep_source_updated_at < row.updated_at


def apply_sitrep_to_session(
    row: CaptureSession,
    generated: GeneratedReport,
    *,
    source_updated_at: datetime,
    report_id: str | None = None,
) -> None:
    row.sitrep_markdown = generated.markdown
    row.sitrep_final_markdown = generated.final_markdown
    row.sitrep_fact_table = generated.fact_table.model_dump(mode="json")
    row.sitrep_violations = [item.model_dump(mode="json") for item in generated.violations]
    row.sitrep_status = generated.status
    row.sitrep_generated_at = _naive(generated.fact_table.generated_at)
    row.sitrep_source_updated_at = _naive(source_updated_at)
    if report_id is not None:
        row.report_id = report_id


def save_sitrep_preview(
    db: Session,
    row: CaptureSession,
    generated: GeneratedReport,
    source_updated_at: datetime,
) -> CaptureSession:
    apply_sitrep_to_session(row, generated, source_updated_at=source_updated_at)
    db.commit()
    db.refresh(row)
    return row


def persist_issued_sitrep(
    db: Session,
    row: CaptureSession,
    generated: GeneratedReport,
    *,
    report_id: str,
    source_updated_at: datetime,
) -> CaptureSession:
    apply_sitrep_to_session(
        row, generated, source_updated_at=source_updated_at, report_id=report_id
    )
    db.commit()
    db.refresh(row)
    return row
