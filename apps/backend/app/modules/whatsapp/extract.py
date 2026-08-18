import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.llm import LLMClient
from app.modules.sitreps.models import LOG_CATEGORIES, LOG_STATUSES
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS
from app.modules.whatsapp.parse import ParsedMessage, redact_phones
from app.modules.whatsapp.prompt import SYSTEM_PROMPT

CHUNK_CHAR_LIMIT = 12_000

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ProposedIncident(BaseModel):
    corporation: str | None = None
    community: str | None = None
    street: str | None = None
    incident_type: str | None = None
    incident_summary: str
    event_date: str | None = None
    injuries_count: int | None = None
    deaths_count: int | None = None
    source_index: int
    source_quote: str

    @field_validator("corporation", mode="before")
    @classmethod
    def canonical_or_none(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        if cleaned in CANONICAL_CORPORATIONS:
            return cleaned
        return None


class ProposedLog(BaseModel):
    corporation: str | None = None
    category: str = "other"
    statement: str
    item: str | None = None
    quantity: float | None = None
    unit: str | None = None
    status: str | None = None
    source_index: int
    source_quote: str

    @field_validator("corporation", mode="before")
    @classmethod
    def canonical_or_none(cls, value: Any) -> str | None:
        return ProposedIncident.canonical_or_none(value)

    @field_validator("category", mode="before")
    @classmethod
    def known_category(cls, value: Any) -> str:
        if isinstance(value, str) and value.strip().lower() in LOG_CATEGORIES:
            return value.strip().lower()
        return "other"

    @field_validator("status", mode="before")
    @classmethod
    def known_status(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str) and value.strip().lower() in LOG_STATUSES:
            return value.strip().lower()
        return None


class ExtractionResult(BaseModel):
    incidents: list[ProposedIncident] = Field(default_factory=list)
    logs: list[ProposedLog] = Field(default_factory=list)


class DraftIncident(ProposedIncident):
    included: bool = True


class DraftLog(ProposedLog):
    included: bool = True


def default_included(corporation: str | None) -> bool:
    return corporation is not None


def to_draft_incidents(incidents: list[ProposedIncident]) -> list[DraftIncident]:
    return [
        DraftIncident(
            **incident.model_dump(),
            included=default_included(incident.corporation),
        )
        for incident in incidents
    ]


def to_draft_logs(logs: list[ProposedLog]) -> list[DraftLog]:
    return [
        DraftLog(**log.model_dump(), included=default_included(log.corporation))
        for log in logs
    ]


def redact_draft_incidents(incidents: list[DraftIncident]) -> list[DraftIncident]:
    redacted: list[DraftIncident] = []
    for incident in incidents:
        summary, _ = redact_phones(incident.incident_summary)
        quote, _ = redact_phones(incident.source_quote)
        community, _ = redact_phones(incident.community or "")
        street, _ = redact_phones(incident.street or "")
        redacted.append(
            incident.model_copy(
                update={
                    "incident_summary": summary,
                    "source_quote": quote,
                    "community": community or None,
                    "street": street or None,
                }
            )
        )
    return redacted


def redact_draft_logs(logs: list[DraftLog]) -> list[DraftLog]:
    redacted: list[DraftLog] = []
    for log in logs:
        statement, _ = redact_phones(log.statement)
        quote, _ = redact_phones(log.source_quote)
        item, _ = redact_phones(log.item or "")
        redacted.append(
            log.model_copy(
                update={
                    "statement": statement,
                    "source_quote": quote,
                    "item": item or None,
                }
            )
        )
    return redacted


def serialize_messages(messages: list[ParsedMessage]) -> str:
    lines = []
    for message in messages:
        sender, _ = redact_phones(message.sender)
        body, _ = redact_phones(message.body)
        lines.append(f"[{message.index}] {sender}: {body}")
    return "\n".join(lines)


def _chunk_messages(messages: list[ParsedMessage]) -> list[list[ParsedMessage]]:
    if not messages:
        return []
    chunks: list[list[ParsedMessage]] = []
    current: list[ParsedMessage] = []
    current_len = 0
    for message in messages:
        serialized = serialize_messages([message])
        extra = len(serialized) + (1 if current else 0)
        if current and current_len + extra > CHUNK_CHAR_LIMIT:
            chunks.append(current)
            current = [message]
            current_len = len(serialized)
        else:
            current.append(message)
            current_len += extra
    if current:
        chunks.append(current)
    return chunks


def parse_model_json(raw: str) -> dict:
    stripped = raw.strip()
    stripped = _FENCE_RE.sub("", stripped).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("model JSON must be an object with incidents and logs")
    return payload


def coerce_draft_incidents(raw_list: list | None) -> list[DraftIncident]:
    incidents: list[DraftIncident] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        try:
            incident = ProposedIncident.model_validate(raw)
        except ValidationError:
            continue
        included = raw.get("included")
        if incident.corporation is None:
            included = False
        elif included is None:
            included = True
        incidents.append(
            DraftIncident(**incident.model_dump(), included=bool(included))
        )
    return incidents


def coerce_draft_logs(raw_list: list | None) -> list[DraftLog]:
    logs: list[DraftLog] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        try:
            log = ProposedLog.model_validate(raw)
        except ValidationError:
            continue
        included = raw.get("included")
        if log.corporation is None:
            included = False
        elif included is None:
            included = True
        logs.append(DraftLog(**log.model_dump(), included=bool(included)))
    return logs


def _coerce_proposals(payload: dict) -> ExtractionResult:
    incidents: list[ProposedIncident] = []
    for raw in payload.get("incidents") or []:
        if not isinstance(raw, dict):
            continue
        try:
            incidents.append(ProposedIncident.model_validate(raw))
        except ValidationError:
            continue
    logs: list[ProposedLog] = []
    for raw in payload.get("logs") or []:
        if not isinstance(raw, dict):
            continue
        try:
            logs.append(ProposedLog.model_validate(raw))
        except ValidationError:
            continue
    return ExtractionResult(incidents=incidents, logs=logs)


def extract_proposals(
    messages: list[ParsedMessage], llm_client: LLMClient
) -> ExtractionResult:
    if not messages:
        return ExtractionResult()

    incidents: list[ProposedIncident] = []
    logs: list[ProposedLog] = []
    for chunk in _chunk_messages(messages):
        user_content = serialize_messages(chunk)
        raw = llm_client.generate(SYSTEM_PROMPT, user_content)
        parsed = _coerce_proposals(parse_model_json(raw))
        incidents.extend(parsed.incidents)
        logs.extend(parsed.logs)
    return ExtractionResult(incidents=incidents, logs=logs)
