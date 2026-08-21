import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import ValidationError

from app.core.llm import LLMClient
from app.modules.capture.missing import missing_fields
from app.modules.capture.numbers import (
    extract_numbers,
    numbers_from_working_set,
    strip_invented_numbers,
)
from app.modules.capture.prompt import SYSTEM_PROMPT
from app.modules.capture.provenance import pin_manual_fields
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureLog,
    CaptureMessage,
    CaptureWorkingSet,
    MissingField,
)
from app.modules.capture.stream_json import AssistantMessageExtractor
from app.modules.sitreps.parse import normalize_corp_incident_type
from app.modules.whatsapp.extract import parse_model_json

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coerce_incident(raw: dict) -> CaptureIncident | None:
    if not isinstance(raw, dict):
        return None
    payload = dict(raw)
    raw_type = payload.get("incident_type")
    mapped, unmapped = normalize_corp_incident_type(
        raw_type if isinstance(raw_type, str) else None
    )
    payload["incident_type"] = mapped
    payload["raw_incident_type"] = unmapped
    try:
        return CaptureIncident.model_validate(payload)
    except ValidationError:
        return None


def _coerce_log(raw: dict) -> CaptureLog | None:
    if not isinstance(raw, dict):
        return None
    try:
        log = CaptureLog.model_validate(raw)
    except ValidationError:
        return None
    if not log.statement.strip():
        return None
    return log


RowT = TypeVar("RowT", CaptureIncident, CaptureLog)


def _is_usable_explicit_id(row_id: str | None) -> bool:
    """A model-supplied row_id is usable verbatim only if it cannot be
    mistaken for part of a field path. The path grammar is
    ``<kind>:<row_id>.<field>``, so an id containing "." or ":" would let a
    row's own id swallow (or be swallowed by) a neighbouring path segment.
    Such an id is treated as though it were never supplied.
    """
    return bool(row_id) and "." not in row_id and ":" not in row_id


def _assign_row_ids(rows: list[RowT]) -> list[RowT]:
    """Give every row a stable, unique row_id, without letting an id-less
    row steal an id that a later row in the same list already owns.

    Two passes:
    1. Reserve every explicitly-provided, non-empty, delimiter-safe row_id
       across all rows. An id containing "." or ":" is not reserved — it is
       structurally incapable of round-tripping through the field-path
       grammar, so it is discarded rather than kept.
    2. Walk the rows in order. A row whose explicit id is reserved and not
       yet used keeps it (first occurrence wins on duplicates). Anything
       else (missing id, delimiter-unsafe id, or an id already used by an
       earlier row) gets the lowest positive integer id that is neither
       reserved nor already used.
    """
    reserved: set[str] = {row.row_id for row in rows if _is_usable_explicit_id(row.row_id)}

    used: set[str] = set()
    next_id = 1
    result: list[RowT] = []
    for row in rows:
        row_id = row.row_id
        if _is_usable_explicit_id(row_id) and row_id not in used:
            used.add(row_id)
        else:
            while str(next_id) in reserved or str(next_id) in used:
                next_id += 1
            row_id = str(next_id)
            used.add(row_id)
            row = row.model_copy(update={"row_id": row_id})
        result.append(row)
    return result


def coerce_working_set(raw: dict, previous: CaptureWorkingSet) -> CaptureWorkingSet:
    capture_raw = raw.get("capture", raw)
    if not isinstance(capture_raw, dict):
        capture_raw = {}

    as_at = capture_raw.get("as_at") or previous.as_at
    incidents = _assign_row_ids(
        [
            incident
            for incident in (
                _coerce_incident(item if isinstance(item, dict) else {})
                for item in capture_raw.get("incidents") or []
            )
            if incident is not None
        ]
    )
    logs = _assign_row_ids(
        [
            log
            for log in (
                _coerce_log(item if isinstance(item, dict) else {})
                for item in capture_raw.get("logs") or []
            )
            if log is not None
        ]
    )

    payload = {
        "as_at": as_at,
        "alert_level": capture_raw.get("alert_level", previous.alert_level),
        "present_activity": capture_raw.get(
            "present_activity", previous.present_activity
        ),
        "situation_overview": capture_raw.get(
            "situation_overview", previous.situation_overview
        ),
        "incidents": [row.model_dump() for row in incidents],
        "logs": [row.model_dump() for row in logs],
    }
    return CaptureWorkingSet.model_validate(payload)


_UNREADABLE = (
    "I could not read that update. Please try again in a short sentence."
)
_FALLBACK_ASSISTANT = (
    "Captured. Tell me what else to add, or correct anything that looks wrong."
)


@dataclass
class TurnComplete:
    working: CaptureWorkingSet
    assistant_message: str
    missing: list[MissingField]
    messages: list[CaptureMessage]


def _history(messages: list[CaptureMessage] | list[dict]) -> list[CaptureMessage]:
    return [
        msg if isinstance(msg, CaptureMessage) else CaptureMessage.model_validate(msg)
        for msg in messages
    ]


def _prompt_payload(
    working: CaptureWorkingSet,
    history: list[CaptureMessage],
    cleaned: str,
) -> str:
    gaps = missing_fields(working)
    payload = {
        "capture": working.model_dump(mode="json"),
        "missing": [item.model_dump() for item in gaps],
        "manual": list(working.manual_fields),
        "messages": [
            {"role": msg.role, "content": msg.content} for msg in history[-12:]
        ],
        "user_message": cleaned,
    }
    return json.dumps(payload)


def _finish_turn(
    working: CaptureWorkingSet,
    history: list[CaptureMessage],
    user_entry: CaptureMessage,
    raw: str,
) -> TurnComplete:
    try:
        parsed = parse_model_json(raw)
    except ValueError:
        assistant = CaptureMessage(
            role="assistant",
            content=_UNREADABLE,
            created_at=_now(),
        )
        return TurnComplete(
            working=working,
            assistant_message=assistant.content,
            missing=missing_fields(working),
            messages=[*history, user_entry, assistant],
        )

    allowed = extract_numbers(user_entry.content) | numbers_from_working_set(
        working.model_dump(mode="json")
    )
    parsed = strip_invented_numbers(parsed, allowed)
    next_working = pin_manual_fields(coerce_working_set(parsed, working), working)
    assistant_text = parsed.get("assistant_message")
    if not isinstance(assistant_text, str) or not assistant_text.strip():
        assistant_text = _FALLBACK_ASSISTANT
    assistant = CaptureMessage(
        role="assistant", content=assistant_text.strip(), created_at=_now()
    )
    return TurnComplete(
        working=next_working,
        assistant_message=assistant.content,
        missing=missing_fields(next_working),
        messages=[*history, user_entry, assistant],
    )


def apply_turn(
    working: CaptureWorkingSet,
    messages: list[CaptureMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
) -> tuple[CaptureWorkingSet, str, list[MissingField], list[CaptureMessage]]:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = CaptureMessage(role="user", content=cleaned, created_at=_now())
    raw = llm_client.generate(SYSTEM_PROMPT, _prompt_payload(working, history, cleaned))
    done = _finish_turn(working, history, user_entry, raw)
    return done.working, done.assistant_message, done.missing, done.messages


def stream_turn(
    working: CaptureWorkingSet,
    messages: list[CaptureMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
) -> Iterator[str | TurnComplete]:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = CaptureMessage(role="user", content=cleaned, created_at=_now())
    prompt = _prompt_payload(working, history, cleaned)
    generate_stream = getattr(llm_client, "generate_stream", None)
    chunks = (
        generate_stream(SYSTEM_PROMPT, prompt)
        if callable(generate_stream)
        else [llm_client.generate(SYSTEM_PROMPT, prompt)]
    )

    extractor = AssistantMessageExtractor()
    raw_parts: list[str] = []
    for chunk in chunks:
        raw_parts.append(chunk)
        delta = extractor.feed(chunk)
        if delta:
            yield delta
    yield _finish_turn(working, history, user_entry, "".join(raw_parts))
