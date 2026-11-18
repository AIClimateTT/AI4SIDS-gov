import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.sitreps.models import ALERT_LEVELS, LOG_CATEGORIES, LOG_STATUSES

# Text that means "nothing here". Officers type these into boxes, and str(None)
# has reached a filing as the alert wording "None".
_BLANK_TEXT = frozenset({"none", "null", "n/a", "na", "nil", "-", "--", "—", "unknown", "tbd"})

# Words that describe a place without naming it. Stored as a community they
# read as a real location on the filing and hide that the place is unknown.
_PLACEHOLDER_PLACE = re.compile(
    r"^(?:an?\s+|the\s+|one\s+)?(?:unnamed|unknown|unspecified|undisclosed|some|"
    r"low[- ]?lying|affected|various|several|multiple)?\s*"
    r"(?:road|roadway|street|community|communities|area|areas|place|location|village|"
    r"region|district|neighbou?rhood)s?"
    r"(?:\s+(?:in|of)\s+(?:our|your|the)\s+(?:corporation|region|borough|area))?$",
    re.IGNORECASE,
)
_AREA_SUFFIX = re.compile(r"\s+area$", re.IGNORECASE)


def blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() in _BLANK_TEXT:
            return None
        return stripped
    return value


def clean_place(value: object) -> object:
    value = blank_to_none(value)
    if not isinstance(value, str):
        return value
    if _PLACEHOLDER_PLACE.match(value):
        return None
    # "Coalmine area" names Coalmine; the suffix is how people talk, not the place.
    return _AREA_SUFFIX.sub("", value) or None


_LEVEL_WORDS = {
    "discontinued": re.compile(r"\b(discontinued|cancell?ed|lifted|ended)\b", re.I),
    "red": re.compile(r"\bred\b", re.I),
    "orange": re.compile(r"\borange\b", re.I),
    "yellow": re.compile(r"\byellow\b", re.I),
    "green": re.compile(r"\bgreen\b", re.I),
}
_ALERT_WORDS = re.compile(
    r"\b(alert|warning|watch|advisory|bulletin|level|discontinued|met\b|ttms|"
    r"red|orange|yellow|green)\b",
    re.I,
)


def level_from_alert_detail(detail: str | None) -> str | None:
    """The colour an alert's own wording names, if it names exactly one."""
    if not detail:
        return None
    if _LEVEL_WORDS["discontinued"].search(detail):
        return "discontinued"
    named = [
        level
        for level in ("red", "orange", "yellow", "green")
        if _LEVEL_WORDS[level].search(detail)
    ]
    return named[0] if len(named) == 1 else None


def reads_like_alert(detail: str) -> bool:
    return bool(_ALERT_WORDS.search(detail))


IncidentScope = Literal["area", "household"]


class CaptureIncident(BaseModel):
    row_id: str = ""
    # area: a community or set of streets, counted in aggregate ("24 homes").
    # household: one property, the unit Survey123 later verifies.
    incident_scope: IncidentScope | None = None
    community: str | None = None
    street: str | None = None
    house_number: str | None = None
    incident_type: str | None = None
    raw_incident_type: str | None = None
    incident_summary: str | None = None
    event_date: str | None = None
    injuries_occurred: bool | None = None
    injuries_count: int | None = None
    deaths_occurred: bool | None = None
    deaths_count: int | None = None
    building_damage: str | None = None
    special_needs_occupants: int | None = None
    households_affected: int | None = None
    persons_affected: int | None = None
    persons_displaced: int | None = None
    persons_marooned: int | None = None
    access_blocked: bool | None = None
    estimated_damage_cost: float | None = None
    action_taken: str | None = None
    relief_supplied: bool | None = None
    forwarded_to_agency: bool | None = None
    further_assessment_required: bool | None = None
    other_follow_up: bool | None = None

    @field_validator(
        "incident_type",
        "raw_incident_type",
        "incident_summary",
        "event_date",
        "building_damage",
        "action_taken",
        "house_number",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        return blank_to_none(value)

    @field_validator("community", "street", mode="before")
    @classmethod
    def named_place_only(cls, value: object) -> object:
        return clean_place(value)

    @field_validator("incident_scope", mode="before")
    @classmethod
    def known_scope(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in ("area", "household"):
            return value.strip().lower()
        return None

    def is_blank(self) -> bool:
        return not any(
            (
                self.incident_type,
                self.raw_incident_type,
                self.incident_summary,
                self.community,
                self.street,
                self.house_number,
            )
        )


class CaptureLog(BaseModel):
    row_id: str = ""
    category: str = "other"
    statement: str = ""
    item: str | None = None
    quantity: float | None = None
    unit: str | None = None
    status: str | None = None

    @field_validator("statement", mode="before")
    @classmethod
    def statement_text(cls, value: object) -> object:
        return blank_to_none(value) or ""

    @field_validator("item", "unit", mode="before")
    @classmethod
    def optional_text(cls, value: object) -> object:
        return blank_to_none(value)

    @field_validator("category", mode="before")
    @classmethod
    def known_category(cls, value: object) -> str:
        if isinstance(value, str) and value.strip().lower() in LOG_CATEGORIES:
            return value.strip().lower()
        return "other"

    @field_validator("status", mode="before")
    @classmethod
    def known_status(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str) and value.strip().lower() in LOG_STATUSES:
            return value.strip().lower()
        return None


class CaptureWorkingSet(BaseModel):
    as_at: datetime | None = None
    alert_level: str = "none"
    alert_detail: str | None = None
    present_activity: str | None = None
    situation_overview: str | None = None
    incidents: list[CaptureIncident] = Field(default_factory=list)
    logs: list[CaptureLog] = Field(default_factory=list)
    manual_fields: list[str] = Field(default_factory=list)

    @field_validator("alert_level", mode="before")
    @classmethod
    def known_alert(cls, value: object) -> str:
        if isinstance(value, str) and value.strip().lower() in ALERT_LEVELS:
            return value.strip().lower()
        return "none"

    @field_validator("alert_detail", "present_activity", "situation_overview", mode="before")
    @classmethod
    def blank_text(cls, value: object) -> object:
        return blank_to_none(value)

    def without_blank_rows(self) -> "CaptureWorkingSet":
        """What gets filed or reported. "+ Add manually" saves an empty row
        before the officer types into it; one left empty is a form, not a
        record, and must not reach a filing as an [other] log with no text."""
        return self.model_copy(
            update={
                "incidents": [row for row in self.incidents if not row.is_blank()],
                "logs": [row for row in self.logs if row.statement.strip()],
            }
        )

    @model_validator(mode="after")
    def consistent(self) -> "CaptureWorkingSet":
        # The wording is what the Met Office issued; the level is derived from
        # it, so the two can never disagree on a filing.
        derived = level_from_alert_detail(self.alert_detail)
        if derived is not None:
            self.alert_level = derived
        return self


class CaptureMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class MissingField(BaseModel):
    path: str
    message: str
