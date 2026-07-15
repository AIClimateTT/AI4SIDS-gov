import logging
import re

logger = logging.getLogger(__name__)

CANONICAL_CORPORATIONS = frozenset(
    {
        "san_juan_laventille_regional_co",
        "tunapuna_piarco_regional_corpor",
        "sangre_grande_regional_corporat",
        "penal_debe_regional_corporation",
        "couva_tabaquite_talparo_regiona",
        "mayaro_rio_claro_regional_corpo",
        "siparia_regional_corporation",
        "princes_town_regional_corporati",
        "diego_martin_regional_corporati",
        "san_fernando_city_corporation",
        "chaguanas_borough_corporation",
        "port_of_spain_city_corporation",
        "point_fortin_borough_corporatio",
        "arima_borough_corporation",
    }
)

CANONICAL_INCIDENT_TYPES = frozenset(
    {
        "flooding_",
        "other",
        "landslide",
        "over grown tree",
        "fire",
        "blown_off_roof",
        "fallen_tree",
        "earthquake",
    }
)

FOLLOW_UP_TOKEN_MAP = {
    "Supply_Relief_Items_": "relief_supplied",
    "Forward_to_Other_Agency": "forwarded_to_agency",
    "Further_Assessment_Required_": "further_assessment_required",
    "other": "other",
}

OVERFLOW_PERSONS_RE = re.compile(r"^(\d+)\s*persons?$", re.IGNORECASE)


def normalize_corporation(raw: str | None) -> tuple[str | None, str | None]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, None
    lowered = cleaned.lower()
    if lowered in CANONICAL_CORPORATIONS:
        return lowered, None
    logger.warning("unmapped Municipal Boundary value: %r", cleaned)
    return "unmapped", cleaned


def normalize_incident_type(raw: str | None) -> tuple[str | None, str | None]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, None
    lowered = cleaned.lower()
    if lowered in CANONICAL_INCIDENT_TYPES:
        return lowered, None
    logger.warning("unmapped Incident Type value: %r", cleaned)
    return "unmapped", cleaned


def normalize_validation_status(raw: str | None) -> str:
    cleaned = (raw or "").strip().lower()
    if cleaned == "validated":
        return "validated"
    if cleaned == "":
        return "pending"
    logger.warning("unexpected Validated/NotValidated value: %r", raw)
    return "pending"


def parse_occupants(household_occupants_raw: str | None, overflow_raw: str | None) -> int | None:
    cleaned = (household_occupants_raw or "").strip()
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.lower() == "other":
        overflow = (overflow_raw or "").strip()
        if overflow.isdigit():
            return int(overflow)
        match = OVERFLOW_PERSONS_RE.match(overflow)
        if match:
            return int(match.group(1))
        logger.warning("could not parse overflow occupants value: %r", overflow_raw)
        return None
    return None


def parse_follow_up_flags(raw: str | None) -> dict[str, bool]:
    flags = {
        "relief_supplied": False,
        "forwarded_to_agency": False,
        "further_assessment_required": False,
        "other": False,
    }
    cleaned = (raw or "").strip()
    if not cleaned:
        return flags
    for token in cleaned.split(","):
        token = token.strip()
        key = FOLLOW_UP_TOKEN_MAP.get(token)
        if key:
            flags[key] = True
        else:
            logger.warning("unmapped Follow Up Recommendation token: %r", token)
    return flags
