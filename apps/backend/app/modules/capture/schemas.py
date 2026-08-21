from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.sitreps.models import ALERT_LEVELS, LOG_CATEGORIES, LOG_STATUSES


class CaptureIncident(BaseModel):
    row_id: str = ""
    community: str | None = None
    street: str | None = None
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
    estimated_damage_cost: float | None = None
    action_taken: str | None = None
    relief_supplied: bool | None = None
    forwarded_to_agency: bool | None = None
    further_assessment_required: bool | None = None
    other_follow_up: bool | None = None

    @field_validator(
        "community",
        "street",
        "incident_type",
        "raw_incident_type",
        "incident_summary",
        "event_date",
        "building_damage",
        "action_taken",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class CaptureLog(BaseModel):
    row_id: str = ""
    category: str = "other"
    statement: str = ""
    item: str | None = None
    quantity: float | None = None
    unit: str | None = None
    status: str | None = None

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


class CaptureMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class MissingField(BaseModel):
    path: str
    message: str
