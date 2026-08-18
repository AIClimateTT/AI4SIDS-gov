import json

from app.core.llm import LLMClient
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

    payload = {
        "incidents": [row.model_dump() for row in incidents],
        "logs": [row.model_dump() for row in logs],
        "instruction": cleaned,
    }
    raw = llm_client.generate(ADJUST_PROMPT, json.dumps(payload))
    parsed = parse_model_json(raw)
    return coerce_draft_incidents(parsed.get("incidents")), coerce_draft_logs(
        parsed.get("logs")
    )
