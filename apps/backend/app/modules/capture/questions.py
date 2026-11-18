"""The clerk's follow-up questions, asked by code from what is still missing.

The model used to pick questions from a "missing" list computed before the
turn, so they lagged a turn behind: Chaguanas' Nov 18 opening message left two
dates and a casualty answer open and the clerk asked nothing. Code knows the
gaps after the turn exactly, so it asks."""

import re

from app.modules.capture.schemas import CaptureIncident, CaptureWorkingSet, MissingField

MAX_QUESTIONS = 2

_INDEX_RE = re.compile(r"^incidents\[(\d+)\]\.(\w+)$")

_TYPE_WORDS = {
    "flooding_": "flooding",
    "blown_off_roof": "blown-off roof",
    "fallen_tree": "fallen tree",
    "over grown tree": "overgrown tree",
}

# Most useful first: where, what and when before casualties and house numbers.
_ORDER = (
    "alert_level",
    "community",
    "incident_type",
    "event_date",
    "casualties",
    "house_number",
    "alert_detail",
)


def incident_type_display(kind: str) -> str:
    """'flooding_' → 'flooding', 'blown_off_roof' → 'blown-off roof'."""
    return (_TYPE_WORDS.get(kind) or kind).replace("_", " ").strip()


def incident_label(incident: CaptureIncident) -> str:
    kind = incident.incident_type or ""
    if kind == "other" and incident.raw_incident_type:
        words = incident.raw_incident_type
    else:
        words = incident_type_display(kind) if kind else ""
    words = words or "incident"
    if incident.incident_scope == "household" and incident.house_number:
        place = f"{incident.house_number} {incident.street or incident.community or ''}".strip()
    else:
        place = incident.street or incident.community
    return f"the {words} at {place}" if place else f"the {words} (incident {incident.row_id})"


def _join(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def _question(field: str, labels: list[str]) -> str | None:
    if field == "alert_level":
        return "Has the Met Office issued an alert for your region, and at what level?"
    if field == "alert_detail":
        return (
            "The alert wording does not read like a Met Office alert. "
            "What does the alert say?"
        )
    if not labels:
        return None
    if field == "community":
        return f"Where is {_join(labels)}? A community or street name is enough."
    if field == "incident_type":
        return f"What kind of incident is {_join(labels)}?"
    if field == "event_date":
        return f"What day did {_join(labels)} happen?"
    if field == "casualties":
        return f"Were there any injuries or deaths at {_join(labels)}?"
    if field == "house_number":
        return f"What is the house number or LP for {_join(labels)}?"
    return None


def missing_questions(
    missing: list[MissingField],
    working: CaptureWorkingSet,
    recently_asked: str = "",
    asked_before: str = "",
) -> list[str]:
    """Up to MAX_QUESTIONS plain questions about what is still missing.

    A question already in the clerk's last reply is skipped, so an officer
    who answers something else is not asked the same thing every turn; it
    comes back once they have moved on. The alert question is asked once per
    session: "none" is a legal answer the record cannot tell from the default
    ("not at this time", Point Fortin), so asking again would nag."""
    by_field: dict[str, list[str]] = {}
    for item in missing:
        match = _INDEX_RE.match(item.path)
        if match:
            index, field = int(match.group(1)), match.group(2)
            if index < len(working.incidents):
                by_field.setdefault(field, []).append(incident_label(working.incidents[index]))
        else:
            by_field.setdefault(item.path, [])
    questions: list[str] = []
    for field in _ORDER:
        if field not in by_field:
            continue
        question = _question(field, by_field[field])
        if field == "alert_level" and question and question in asked_before:
            continue
        if question and question not in recently_asked:
            questions.append(question)
        if len(questions) == MAX_QUESTIONS:
            break
    return questions
