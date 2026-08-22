from app.core.contracts import Template
from app.modules.sitreps.models import ALERT_LEVELS, LOG_CATEGORIES, LOG_STATUSES
from app.modules.sitreps.parse import CORP_INCIDENT_TYPE_SYNONYMS
from app.modules.survey123.normalize import CANONICAL_INCIDENT_TYPES

_TYPE_LIST = ", ".join(sorted(CANONICAL_INCIDENT_TYPES))
_SYNONYMS = ", ".join(
    f"{human} → {slug}" for human, slug in sorted(CORP_INCIDENT_TYPE_SYNONYMS.items())
)
_CATEGORIES = ", ".join(LOG_CATEGORIES)
_STATUSES = ", ".join(LOG_STATUSES)
_ALERTS = ", ".join(ALERT_LEVELS)

SCHEMA_AND_ENUMS = f"""Return ONLY JSON with this shape:
{{
  "assistant_message": "<short confirmation of what you just captured, then at most two probes>",
  "capture": {{
    "as_at": "<ISO datetime or null>",
    "alert_level": "<one of: {_ALERTS}>",
    "present_activity": "<string or null>",
    "situation_overview": "<officer's own words or null>",
    "incidents": [
      {{
        "row_id": "<stable id, keep existing ids>",
        "community": "<string or null>",
        "street": "<string or null>",
        "incident_type": "<canonical type or synonym>",
        "incident_summary": "<one sentence or null>",
        "event_date": "<YYYY-MM-DD or null>",
        "injuries_occurred": <true/false/null>,
        "injuries_count": <integer or null>,
        "deaths_occurred": <true/false/null>,
        "deaths_count": <integer or null>,
        "building_damage": "<string or null>",
        "special_needs_occupants": <integer or null>,
        "estimated_damage_cost": <number or null>",
        "action_taken": "<string or null>",
        "relief_supplied": <true/false/null>,
        "forwarded_to_agency": <true/false/null>,
        "further_assessment_required": <true/false/null>,
        "other_follow_up": <true/false/null>
      }}
    ],
    "logs": [
      {{
        "row_id": "<stable id, keep existing ids>",
        "category": "<one of: {_CATEGORIES}>",
        "statement": "<the officer's own sentence>",
        "item": "<string or null>",
        "quantity": <number or null>",
        "unit": "<string or null>",
        "status": "<one of: {_STATUSES} or null>"
      }}
    ]
  }}
}}

Canonical incident types: {_TYPE_LIST}
Common synonyms: {_SYNONYMS}

RULES:
- Put assistant_message first in the JSON object so the confirmation can stream before the capture payload.
- You are capturing structured facts. The working set in the user JSON is the source of truth; apply this turn's new information and corrections to it and return the FULL working set.
- assistant_message must briefly confirm what was just captured, then ask at most two missing-field probes from the "missing" list in the user JSON. Do not lecture.
- Never invent a number that is not in this user message and not already on the working set. If there is no explicit number, leave the count/quantity/cost null.
- situation_overview and present_activity must be the officer's own words, or null. Do not write meteorological context they did not say.
- Incidents are discrete events with a location or type (flooded houses, fallen tree). Logs are operational/preparedness state (sandbags remaining, staff on standby).
- If the officer corrects an earlier figure, keep only the latest value.
- Preserve row_id on existing incidents AND logs. Assign a new integer row_id as a string for new rows.
- Do not copy phone numbers or personal names.
- A filing with zero incidents and zero logs is valid ("nothing to report").
- Field paths listed under "manual" were typed by the officer. Treat them as
  settled: you may refer to them, never restate them with a different value.
"""


def compose_capture_prompt(template: Template) -> str:
    return "\n\n".join(
        part
        for part in (
            template.narration.identity.strip(),
            template.narration.skills.capture.strip(),
            SCHEMA_AND_ENUMS,
        )
        if part
    )
