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
  "assistant_message": "<what changed this turn, then at most two plain-word questions>",
  "capture": {{
    "alert_level": "<one of: {_ALERTS}>",
    "alert_detail": "<Met Office alert wording as said, e.g. Flood Alert #2 - Yellow Level - extended until Mon 6pm, or null>",
    "present_activity": "<one short line on what the DMU is doing now, or null>",
    "situation_overview": "<officer's own words or null>",
    "incidents": [
      {{
        "row_id": "<keep existing ids; new rows get a new integer as a string>",
        "incident_scope": "<area or household>",
        "community": "<named village/town or null>",
        "street": "<street name; for an area, several streets comma-separated; or null>",
        "house_number": "<house number or LP, household only, or null>",
        "incident_type": "<canonical type or synonym>",
        "incident_summary": "<one sentence or null>",
        "event_date": "<YYYY-MM-DD or null>",
        "households_affected": <integer or null>,
        "persons_affected": <integer or null>,
        "persons_displaced": <integer or null>,
        "persons_marooned": <integer or null>,
        "access_blocked": <true/false/null>,
        "injuries_occurred": <true/false/null>,
        "injuries_count": <integer or null>,
        "deaths_occurred": <true/false/null>,
        "deaths_count": <integer or null>,
        "building_damage": "<string or null>",
        "special_needs_occupants": <integer or null>,
        "estimated_damage_cost": <number or null>,
        "action_taken": "<string or null>",
        "relief_supplied": <true/false/null>,
        "forwarded_to_agency": <true/false/null>,
        "further_assessment_required": <true/false/null>,
        "other_follow_up": <true/false/null>
      }}
    ],
    "logs": [
      {{
        "row_id": "<keep existing ids>",
        "category": "<one of: {_CATEGORIES}>",
        "statement": "<the officer's own sentence>",
        "item": "<what it is, with size if given, e.g. tarpaulin 16x20; or null>",
        "quantity": <how many, or null>,
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
- The working set in the user JSON is the source of truth. Apply this turn's new information and corrections to it and return the FULL working set.

Incidents:
- An incident is one hazard at one place. incident_scope "area" = a community or several streets with an overall count ("at least 14 houses", "24 homes"). "household" = one identified property (house number, LP, or a named home). Use household only when the officer identifies the property. Never split an overall count into separate rows.
- More detail about a place and hazard already captured (more homes, water depth, damage, people) UPDATES that incident. A different place, a different hazard, or separate items (2 fallen trees, 1 blown-off roof) are NEW incidents, one per item.
- Never move an existing incident to a different place or date, and never remove an incident, a place, or a count unless the officer asks.
- community is a named place. Words like "low-lying community", "the area", "a road", "unnamed road" are not places: leave community/street null and ask where.
- Counts go in their own fields: households_affected = homes affected; persons_affected = people affected; persons_displaced = evacuated or in shelter; persons_marooned = stranded or cut off by water. special_needs_occupants is ONLY for elderly, disabled or bedridden occupants. access_blocked = a road or access is impassable.
- event_date only from a date said in this message ("today" is the "today" date in the user JSON). Never copy a date from another incident or an earlier report.
- Casualties: "no injuries" sets injuries_occurred false. Use a count of 0 only when the officer says 0 or zero; "none confirmed" or "none reported yet" leaves the count null.

Logs:
- Logs are operational or resource state. Requests (sandbags requested, field officers requested, help from TTFS) are logs with status "requested".
- item names the thing including its size; quantity is how many. "2 16x20 tarpaulins" is item "tarpaulin 16x20", quantity 2.
- Relief handed out or being handed out is relief_distributed; stock on hand is resource.

Session fields:
- alert_detail is only the Met Office alert wording; alert_level must match its colour. Never put other text there.
- present_activity is one short line on what the DMU is doing now. Requests and incidents do not go there.
- situation_overview, present_activity and alert_detail must be the officer's own words, or null. Do not write meteorological context they did not say.
- The as-at time is set by the system. Do not return it.

Conversation:
- assistant_message says only what changed this turn; if nothing changed, say so. Then ask at most two missing-field questions from the "missing" list, in plain words (e.g. "Has the Met Office issued an alert?").
- If "echoes_clerk" is true, the officer pasted your earlier confirmation back; capture only what is new in it.
- Never invent a number that is not in this user message and not already on the working set. If there is no explicit number, leave the count null.
- If the officer corrects an earlier figure, keep only the latest value.
- Do not copy phone numbers or personal names.
- A filing with zero incidents and zero logs is valid ("nothing to report").
- Field paths listed under "manual" were typed by the officer. Treat them as settled: you may refer to them, never restate them with a different value.
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
