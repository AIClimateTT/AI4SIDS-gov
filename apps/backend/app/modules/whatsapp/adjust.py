import json

from app.core.llm import LLMClient
from app.modules.capture.numbers import (
    extract_numbers,
    numbers_from_working_set,
    strip_invented_numbers,
)
from app.modules.whatsapp.extract import (
    DraftIncident,
    DraftLog,
    coerce_draft_incidents,
    coerce_draft_logs,
    parse_model_json,
)
from app.modules.whatsapp.prompt import ADJUST_PROMPT


def adjust_working_set(
    incidents: list[DraftIncident],
    logs: list[DraftLog],
    instruction: str,
    llm_client: LLMClient,
) -> tuple[list[DraftIncident], list[DraftLog]]:
    cleaned = instruction.strip()
    if not cleaned:
        raise ValueError("instruction is required")

    current = {
        "incidents": [row.model_dump() for row in incidents],
        "logs": [row.model_dump() for row in logs],
    }
    raw = llm_client.generate(
        ADJUST_PROMPT, json.dumps({**current, "instruction": cleaned})
    )
    parsed = parse_model_json(raw)

    # The same guard the corp capture turn applies (modules/capture/turn.py),
    # and for a sharper reason here. A draft promoted from this screen is
    # ingested as a Submission, so its rows land in `sitrep_incidents` - the
    # authoritative table holding corporations' signed-off figures - and the
    # metric functions do not distinguish them by source. A casualty count the
    # model invented during an adjustment would therefore reach the minister's
    # report cited as a corporation's own return.
    #
    # The model is shown only the current rows and the instruction (never the
    # transcript), so any figure outside those two is invention by definition.
    # Zero is always allowed; it means "none occurred". A figure the officer
    # spelled out in words is dropped rather than trusted - they retype it as
    # digits, which fails safe in the direction that matters.
    allowed = extract_numbers(cleaned) | numbers_from_working_set(current)
    parsed = strip_invented_numbers(parsed, allowed)

    return coerce_draft_incidents(parsed.get("incidents")), coerce_draft_logs(
        parsed.get("logs")
    )
