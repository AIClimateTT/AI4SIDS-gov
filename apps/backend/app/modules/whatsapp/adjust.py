from app.core.llm import LLMClient
from app.modules.whatsapp.extract import DraftIncident, DraftLog, WhatsAppWorkingSet
from app.modules.whatsapp.turn import apply_turn


def adjust_working_set(
    incidents: list[DraftIncident],
    logs: list[DraftLog],
    instruction: str,
    llm_client: LLMClient,
    *,
    as_at=None,
    source_text: str = "",
    source_kind: str = "export",
    messages: list | None = None,
    manual_fields: list[str] | None = None,
) -> tuple[list[DraftIncident], list[DraftLog]]:
    cleaned = instruction.strip()
    if not cleaned:
        raise ValueError("instruction is required")

    working = WhatsAppWorkingSet(
        as_at=as_at,
        incidents=incidents,
        logs=logs,
        manual_fields=list(manual_fields or []),
    )
    next_working, _message, _missing, _messages = apply_turn(
        working,
        messages or [],
        cleaned,
        llm_client,
        source_text=source_text,
        source_kind=source_kind,
    )
    return next_working.incidents, next_working.logs
