"""Which values in a capture session were written by hand.

A capture session mixes two authors: the LLM, which rewrites the whole
working set on every turn, and the officer, who edits fields directly.
Manual values must survive every subsequent turn, so they are recorded as
explicit field paths and re-pinned server-side after the model answers.
Prompt instructions are not a mechanism — this module is.
"""

from collections.abc import Iterable

SESSION_FIELDS = ("as_at", "alert_level", "present_activity", "situation_overview")


def incident_path(row_id: str, field: str) -> str:
    return f"incident:{row_id}.{field}"


def log_path(row_id: str, field: str) -> str:
    return f"log:{row_id}.{field}"


def row_paths(manual: Iterable[str], kind: str, row_id: str) -> set[str]:
    prefix = f"{kind}:{row_id}."
    return {item[len(prefix) :] for item in manual if item.startswith(prefix)}
