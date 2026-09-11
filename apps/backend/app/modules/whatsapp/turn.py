import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.llm import LLMClient
from app.modules.capture.numbers import (
    extract_numbers,
    numbers_from_working_set,
    strip_invented_numbers,
)
from app.modules.capture.schemas import MissingField
from app.modules.capture.stream_json import AssistantMessageExtractor
from app.modules.whatsapp.extract import (
    CHUNK_CHAR_LIMIT,
    WhatsAppMessage,
    WhatsAppWorkingSet,
    coerce_draft_incidents,
    coerce_draft_logs,
    parse_model_json,
    serialize_messages,
)
from app.modules.whatsapp.missing import missing_fields
from app.modules.whatsapp.parse import messages_from_source
from app.modules.whatsapp.prompt import TURN_PROMPT
from app.modules.whatsapp.provenance import pin_manual_fields


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_UNREADABLE = "I could not read that update. Please try again in a short sentence."
_FALLBACK_ASSISTANT = (
    "Updated. Tell me what else to change, or correct anything that looks wrong."
)


@dataclass
class TurnComplete:
    working: WhatsAppWorkingSet
    assistant_message: str
    missing: list[MissingField]
    messages: list[WhatsAppMessage]


def _history(messages: list[WhatsAppMessage] | list[dict]) -> list[WhatsAppMessage]:
    return [
        msg if isinstance(msg, WhatsAppMessage) else WhatsAppMessage.model_validate(msg)
        for msg in messages
    ]


def _source_for_prompt(source_text: str, working: WhatsAppWorkingSet) -> str:
    if not source_text.strip():
        return ""
    parsed, _kind, _pii = messages_from_source(source_text)
    serialized = serialize_messages(parsed) if parsed else source_text
    if len(serialized) <= CHUNK_CHAR_LIMIT:
        return serialized

    quotes: list[str] = []
    seen: set[str] = set()
    for row in (*working.incidents, *working.logs):
        quote = (row.source_quote or "").strip()
        if not quote or quote in seen:
            continue
        seen.add(quote)
        quotes.append(f"[{row.source_index}] {quote}")
    extra = "\n".join(quotes)
    budget = CHUNK_CHAR_LIMIT - len(extra) - (1 if extra else 0)
    if budget <= 0:
        return extra[:CHUNK_CHAR_LIMIT]
    return serialized[-budget:] + (("\n" + extra) if extra else "")


def _prompt_payload(
    working: WhatsAppWorkingSet,
    history: list[WhatsAppMessage],
    cleaned: str,
    source_text: str,
    source_kind: str,
) -> str:
    gaps = missing_fields(working)
    payload = {
        "working": {
            "as_at": working.as_at.isoformat() if working.as_at else None,
            "incidents": [row.model_dump() for row in working.incidents],
            "logs": [row.model_dump() for row in working.logs],
            "manual_fields": list(working.manual_fields),
        },
        "missing": [item.model_dump() for item in gaps],
        "manual": list(working.manual_fields),
        "source_kind": source_kind,
        "source": _source_for_prompt(source_text, working),
        "messages": [
            {"role": msg.role, "content": msg.content} for msg in history[-12:]
        ],
        "user_message": cleaned,
    }
    return json.dumps(payload)


def _raw_working(parsed: dict) -> dict:
    working = parsed.get("working")
    if isinstance(working, dict):
        return working
    return parsed


def coerce_working_set(
    raw: dict, previous: WhatsAppWorkingSet
) -> WhatsAppWorkingSet:
    working_raw = _raw_working(raw)
    as_at = working_raw.get("as_at") or previous.as_at
    incidents = coerce_draft_incidents(working_raw.get("incidents"))
    logs = coerce_draft_logs(working_raw.get("logs"))
    payload = {
        "as_at": as_at,
        "incidents": [row.model_dump() for row in incidents],
        "logs": [row.model_dump() for row in logs],
    }
    return WhatsAppWorkingSet.model_validate(payload)


def _finish_turn(
    working: WhatsAppWorkingSet,
    history: list[WhatsAppMessage],
    user_entry: WhatsAppMessage,
    raw: str,
    source_text: str,
) -> TurnComplete:
    try:
        parsed = parse_model_json(raw)
    except ValueError:
        assistant = WhatsAppMessage(
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

    allowed = (
        extract_numbers(user_entry.content)
        | numbers_from_working_set(working.model_dump(mode="json"))
        | extract_numbers(source_text)
    )
    parsed = strip_invented_numbers(parsed, allowed)
    next_working = pin_manual_fields(coerce_working_set(parsed, working), working)
    assistant_text = parsed.get("assistant_message")
    if not isinstance(assistant_text, str) or not assistant_text.strip():
        assistant_text = _FALLBACK_ASSISTANT
    assistant = WhatsAppMessage(
        role="assistant", content=assistant_text.strip(), created_at=_now()
    )
    return TurnComplete(
        working=next_working,
        assistant_message=assistant.content,
        missing=missing_fields(next_working),
        messages=[*history, user_entry, assistant],
    )


def apply_turn(
    working: WhatsAppWorkingSet,
    messages: list[WhatsAppMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
    *,
    source_text: str = "",
    source_kind: str = "export",
) -> tuple[WhatsAppWorkingSet, str, list[MissingField], list[WhatsAppMessage]]:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = WhatsAppMessage(role="user", content=cleaned, created_at=_now())
    raw = llm_client.generate(
        TURN_PROMPT,
        _prompt_payload(working, history, cleaned, source_text, source_kind),
    )
    done = _finish_turn(working, history, user_entry, raw, source_text)
    return done.working, done.assistant_message, done.missing, done.messages


def stream_turn(
    working: WhatsAppWorkingSet,
    messages: list[WhatsAppMessage] | list[dict],
    user_message: str,
    llm_client: LLMClient,
    *,
    source_text: str = "",
    source_kind: str = "export",
) -> Iterator[str | TurnComplete]:
    cleaned = user_message.strip()
    if not cleaned:
        raise ValueError("message is required")

    history = _history(messages)
    user_entry = WhatsAppMessage(role="user", content=cleaned, created_at=_now())
    prompt = _prompt_payload(working, history, cleaned, source_text, source_kind)
    generate_stream = getattr(llm_client, "generate_stream", None)
    chunks = (
        generate_stream(TURN_PROMPT, prompt)
        if callable(generate_stream)
        else [llm_client.generate(TURN_PROMPT, prompt)]
    )

    extractor = AssistantMessageExtractor()
    raw_parts: list[str] = []
    for chunk in chunks:
        raw_parts.append(chunk)
        delta = extractor.feed(chunk)
        if delta:
            yield delta
    yield _finish_turn(working, history, user_entry, "".join(raw_parts), source_text)
