"""Code-owned lists the corp capture prompt pulls in.

The prompt's text lives in app/prompts/corp_capture and is versioned there.
These lists come from the same enums the schema validates against, so the
prompt cannot drift from what the code accepts. Changing one changes the
prompt's hash, and the registry test asks for a version bump."""

from app.modules.sitreps.models import ALERT_LEVELS, LOG_CATEGORIES, LOG_STATUSES
from app.modules.sitreps.parse import CORP_INCIDENT_TYPE_SYNONYMS
from app.modules.survey123.normalize import CANONICAL_INCIDENT_TYPES

CAPTURE_PROMPT_ID = "corp_capture"


def prompt_variables() -> dict[str, str]:
    return {
        "incident_types": ", ".join(sorted(CANONICAL_INCIDENT_TYPES)),
        "incident_type_synonyms": ", ".join(
            f"{human} → {slug}" for human, slug in sorted(CORP_INCIDENT_TYPE_SYNONYMS.items())
        ),
        "log_categories": ", ".join(LOG_CATEGORIES),
        "log_statuses": ", ".join(LOG_STATUSES),
        "alert_levels": ", ".join(ALERT_LEVELS),
    }
