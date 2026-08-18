from app.core.contracts import NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.engine import GeneratedReport, narrate_fact_table
from app.core.llm import LLMClient
from app.modules.whatsapp.extract import DraftIncident, DraftLog
from app.modules.whatsapp.facts import (
    facts_from_working_set,
    included_attributed_incidents,
    included_attributed_logs,
)

PROVISIONAL_BANNER = (
    "**Provisional — WhatsApp hour briefing, not a cited national SITREP.**"
)

BRIEFING_TEMPLATE = Template(
    name="whatsapp_hour_briefing",
    version=1,
    title="WhatsApp Hour Briefing",
    description="Provisional ministerial note from an unconfirmed WhatsApp extract.",
    params=[TemplateParam(name="as_at", required=True)],
    data_requirements=[],
    narration=NarrationConfig(
        system_prompt=(
            "You are drafting a short provisional hour briefing for the Minister "
            "of Rural Development and Local Government of Trinidad and Tobago, "
            "from a WhatsApp group extract that has not been filed as corporation "
            "SITREPs.\n\n"
            "Every fact is unverified (verification: pending). Say so plainly. "
            "Group by corporation. Lead with incidents and casualties, then "
            "resources and activity. Do not merge or invent totals. Keep it to "
            "one page. Never present this as a signed national SITREP."
        ),
        output_sections=["situation_overview", "by_corporation", "data_gaps"],
    ),
    render=RenderConfig(include_citation_appendix=True),
)


class BriefingError(ValueError):
    pass


def generate_briefing(
    incidents: list[DraftIncident],
    logs: list[DraftLog],
    as_at,
    llm_client: LLMClient,
) -> GeneratedReport:
    included_incidents = included_attributed_incidents(incidents)
    included_logs = included_attributed_logs(logs)
    if not included_incidents and not included_logs:
        raise BriefingError(
            "include at least one row with a corporation to generate a briefing"
        )

    fact_table = facts_from_working_set(incidents, logs, as_at)
    report = narrate_fact_table(BRIEFING_TEMPLATE, fact_table, llm_client, [])
    banner = PROVISIONAL_BANNER + "\n\n"
    if not report.markdown.startswith(PROVISIONAL_BANNER):
        report = report.model_copy(update={"markdown": banner + report.markdown})
    return report
