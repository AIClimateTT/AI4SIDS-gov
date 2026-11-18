import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import ValidationError

from app.core.llm import LLMClient
from app.modules.capture.diff import working_changes
from app.modules.capture.guards import (
    echoes_clerk,
    guard_dropped_rows,
    guard_event_dates,
    guard_zero_counts,
    pinned_field_notes,
    release_alert_on_new_level,
    today_local,
    unchanged_claim_note,
)
from app.modules.capture.missing import missing_fields
from app.modules.capture.model_json import parse_model_json
from app.modules.capture.numbers import (
    extract_numbers,
    numbers_from_working_set,
    strip_invented_numbers,
)
from app.modules.capture.prompt import SCHEMA_AND_ENUMS
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


def _assign_row_ids(rows: list[RowT], taken: set[str] | None = None) -> list[RowT]:
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
    # Ids already on the working set stay theirs even if the model left the
    # row out: a new row must never take the id of one that went missing,
    # or restoring the missing row collides with it.
    reserved |= taken or set()

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

    # The as-at time belongs to the system and the officer, not the model: it
    # is refreshed on each change and pinned when typed. Siparia's sitrep went
    # out "as at" the moment the session opened, three days earlier.
    as_at = previous.as_at
    incidents = _assign_row_ids(
        [
            incident
            for incident in (
                _coerce_incident(item if isinstance(item, dict) else {})
                for item in capture_raw.get("incidents") or []
            )
            if incident is not None
        ],
        {row.row_id for row in previous.incidents},
    )
    logs = _assign_row_ids(
        [
            log
            for log in (
                _coerce_log(item if isinstance(item, dict) else {})
                for item in capture_raw.get("logs") or []
            )
            if log is not None
        ],
        {row.row_id for row in previous.logs},
    )

    payload = {
        "as_at": as_at,
        "alert_level": capture_raw.get("alert_level", previous.alert_level),
        "alert_detail": capture_raw.get("alert_detail", previous.alert_detail),
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
    raw_output: str = ""
    parse_ok: bool = True
    # Corrections to the clerk's own confirmation, sent as a second message.
    notes: list[str] = field(default_factory=list)
    retried: bool = False


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
        "capture": working.model_dump(mode="json", exclude={"as_at"}),
        "missing": [item.model_dump() for item in gaps],
        "manual": list(working.manual_fields),
        "messages": [
            {"role": msg.role, "content": msg.content} for msg in history[-12:]
        ],
        "today": today_local().isoformat(),
        "user_message": cleaned,
        "echoes_clerk": echoes_clerk(
            cleaned, [msg.content for msg in history if msg.role == "assistant"]
        ),
    }
    return json.dumps(payload)


_REPAIR = (
    "\n\nYour previous reply could not be parsed as JSON. Reply again with ONLY "
    "the JSON object described above: no prose, no code fence. Keep assistant_message "
    "to one or two short sentences."
)


def _finish_turn(
    working: CaptureWorkingSet,
    history: list[CaptureMessage],
    user_entry: CaptureMessage,
    raw: str,
    retry=None,
) -> TurnComplete:
    """Turn the model's reply into the next working set.

    `retry`, when given, re-asks the model once for a reply that parses. A turn
    that still fails keeps the officer's message and says so, instead of
    silently losing a report (Chaguanas' blown-off roof)."""
    retried = False
    try:
        parsed = parse_model_json(raw)
    except ValueError:
        parsed = None
        if retry is not None:
            retried = True
            retry_raw = retry()
            raw = f"{raw}\n\n--- retry ---\n{retry_raw}"
            try:
                parsed = parse_model_json(retry_raw)
            except ValueError:
                parsed = None
    if parsed is None:
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
            raw_output=raw,
            parse_ok=False,
            retried=retried,
        )

    allowed = extract_numbers(user_entry.content) | numbers_from_working_set(
        working.model_dump(mode="json")
    )
    parsed = strip_invented_numbers(parsed, allowed)
    proposed = coerce_working_set(parsed, working)
    proposed, date_notes = guard_event_dates(
        proposed, working, user_entry.content, today_local()
    )
    proposed, row_notes = guard_dropped_rows(proposed, working, user_entry.content)
    proposed = guard_zero_counts(proposed, working, user_entry.content)
    pin_basis = release_alert_on_new_level(proposed, working)
    next_working = pin_manual_fields(proposed, pin_basis)
    # Re-run the schema's own consistency (alert level from wording) on the
    # pinned result, which model_copy does not.
    next_working = CaptureWorkingSet.model_validate(next_working.model_dump())

    assistant_text = parsed.get("assistant_message")
    if not isinstance(assistant_text, str) or not assistant_text.strip():
        assistant_text = _FALLBACK_ASSISTANT
    assistant_text = assistant_text.strip()
    changes = working_changes(
        working.model_dump(mode="json"), next_working.model_dump(mode="json")
    )
    notes = [
        *pinned_field_notes(proposed, next_working),
        *row_notes,
        *date_notes,
    ]
    claim = unchanged_claim_note(assistant_text, changes)
    if claim:
        notes.insert(0, claim)

    assistant = CaptureMessage(role="assistant", content=assistant_text, created_at=_now())
    messages = [*history, user_entry, assistant]
    if notes:
        messages.append(
            CaptureMessage(role="assistant", content=" ".join(notes), created_at=_now())
        )
    return TurnComplete(
        working=next_working,
        assistant_message=assistant.content,
        missing=missing_fields(next_working),
        messages=messages,
        raw_output=raw,
        notes=notes,
        retried=retried,
    )


def run_turn(
    working: CaptureWorkingSet,
    messages: list[CaptureMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
    system_prompt: str | None = None,
) -> TurnComplete:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = CaptureMessage(role="user", content=cleaned, created_at=_now())
    assembled = system_prompt if system_prompt is not None else SCHEMA_AND_ENUMS
    prompt = _prompt_payload(working, history, cleaned)
    raw = llm_client.generate(assembled, prompt)
    return _finish_turn(
        working,
        history,
        user_entry,
        raw,
        retry=lambda: llm_client.generate(assembled + _REPAIR, prompt),
    )


def apply_turn(
    working: CaptureWorkingSet,
    messages: list[CaptureMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
    system_prompt: str | None = None,
) -> tuple[CaptureWorkingSet, str, list[MissingField], list[CaptureMessage]]:
    done = run_turn(working, messages, user_message, llm_client, system_prompt)
    return done.working, done.assistant_message, done.missing, done.messages


def stream_turn(
    working: CaptureWorkingSet,
    messages: list[CaptureMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
    system_prompt: str | None = None,
) -> Iterator[str | TurnComplete]:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = CaptureMessage(role="user", content=cleaned, created_at=_now())
    prompt = _prompt_payload(working, history, cleaned)
    assembled = system_prompt if system_prompt is not None else SCHEMA_AND_ENUMS
    generate_stream = getattr(llm_client, "generate_stream", None)
    chunks = (
        generate_stream(assembled, prompt)
        if callable(generate_stream)
        else [llm_client.generate(assembled, prompt)]
    )

    extractor = AssistantMessageExtractor()
    raw_parts: list[str] = []
    for chunk in chunks:
        raw_parts.append(chunk)
        delta = extractor.feed(chunk)
        if delta:
            yield delta
    yield _finish_turn(
        working,
        history,
        user_entry,
        "".join(raw_parts),
        retry=lambda: llm_client.generate(assembled + _REPAIR, prompt),
    )
