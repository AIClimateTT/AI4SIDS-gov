"""Which values in a capture session were written by hand.

A capture session mixes two authors: the LLM, which rewrites the whole
working set on every turn, and the officer, who edits fields directly.
Manual values must survive every subsequent turn, so they are recorded as
explicit field paths and re-pinned server-side after the model answers.
Prompt instructions are not a mechanism — this module is.
"""

from collections.abc import Iterable

from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet

SESSION_FIELDS = ("as_at", "alert_level", "present_activity", "situation_overview")


def incident_path(row_id: str, field: str) -> str:
    return f"incident:{row_id}.{field}"


def log_path(row_id: str, field: str) -> str:
    return f"log:{row_id}.{field}"


def row_paths(manual: Iterable[str], kind: str, row_id: str) -> set[str]:
    prefix = f"{kind}:{row_id}."
    return {item[len(prefix) :] for item in manual if item.startswith(prefix)}


def _pin_rows(
    kind: str,
    next_rows: list,
    previous_rows: list,
    manual: set[str],
    model,
) -> list:
    prior_by_id = {row.row_id: row for row in previous_rows}
    pinned: list = []
    for row in next_rows:
        prior = prior_by_id.get(row.row_id)
        if prior is None:
            pinned.append(row)
            continue
        fields = row_paths(manual, kind, row.row_id) & set(model.model_fields)
        if not fields:
            pinned.append(row)
            continue
        pinned.append(row.model_copy(update={f: getattr(prior, f) for f in fields}))

    # A row the officer created or corrected must not vanish because the model
    # forgot to echo it back.
    returned = {row.row_id for row in pinned}
    for row_id, prior in prior_by_id.items():
        if row_id not in returned and row_paths(manual, kind, row_id):
            pinned.append(prior)
    return pinned


def pin_manual_fields(
    next_working: CaptureWorkingSet, previous: CaptureWorkingSet
) -> CaptureWorkingSet:
    """Restore every hand-written value onto the model's fresh working set."""
    manual = set(previous.manual_fields)
    patch: dict = {"manual_fields": list(previous.manual_fields)}
    if not manual:
        return next_working.model_copy(update=patch)

    for name in SESSION_FIELDS:
        if name in manual:
            patch[name] = getattr(previous, name)

    patch["incidents"] = _pin_rows(
        "incident", next_working.incidents, previous.incidents, manual, CaptureIncident
    )
    patch["logs"] = _pin_rows(
        "log", next_working.logs, previous.logs, manual, CaptureLog
    )
    return next_working.model_copy(update=patch)
