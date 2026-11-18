"""Deterministic checks on what the model returned for one officer message.

The model rewrites the whole working set every turn. Prompt rules ask it not
to drop rows, not to carry a date from one report onto another, and not to
claim a change it did not make; UAT transcripts (Nov 2026) show it does all
three. These guards enforce the rules after the fact and say what they did,
so the officer is told instead of the record quietly disagreeing with the
chat."""

import re
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher, get_close_matches

from app.core.localtime import to_local
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureWorkingSet,
    level_from_alert_detail,
)

_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_FULL_MONTHS = [name for name in _MONTHS if len(name) > 4 or name == "march"]
_WORD_RE = re.compile(r"[a-z]+")
_DAY_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\b")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})\b")
_TODAY_RE = re.compile(r"\b(today|tonight|this (?:morning|afternoon|evening)|now|currently)\b")
# A time of day with no date ("since 2am", "at 1:30 pm", "around midday") is
# a report about today. Chaguanas' Nov 18 test lost both dates to this.
_TIME_OF_DAY_RE = re.compile(
    r"(?<![\d/.-])\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)(?![a-z])"
    r"|\b(?:midday|noon|midnight|this hour|earlier)\b"
)
_YESTERDAY_RE = re.compile(r"\b(yesterday)\b")
# Either day: flooding "since last night", reported the next morning, may be
# dated the night it began or the day it is being dealt with.
_EITHER_DAY_RE = re.compile(r"\b(last night|overnight)\b")
_REMOVAL_RE = re.compile(
    r"\b(remove|delete|drop|scratch|cancel|ignore|disregard|duplicate|"
    r"not an incident|no longer|take (?:it|that) off)\b",
    re.IGNORECASE,
)
_CLAIM_RE = re.compile(
    r"^\s*(captured|updated|recorded|added|noted|set|confirmed|logged)\b", re.IGNORECASE
)

SESSION_LABELS = {
    "as_at": "The as-at time",
    "alert_level": "The alert level",
    "alert_detail": "The alert wording",
    "present_activity": "Present activity",
    "situation_overview": "The situation overview",
}


def today_local() -> date:
    return to_local(datetime.now(timezone.utc)).date()


def dates_in(message: str, today: date) -> set[date]:
    """Every calendar day the message names, in the forms officers use."""
    text = message.lower()
    found: set[date] = set()
    if _TODAY_RE.search(text) or _TIME_OF_DAY_RE.search(text):
        found.add(today)
    if _YESTERDAY_RE.search(text):
        found.add(today - timedelta(days=1))
    if _EITHER_DAY_RE.search(text):
        found |= {today, today - timedelta(days=1)}
    for a, b, c in _NUMERIC_DATE_RE.findall(text):
        first, second, third = int(a), int(b), int(c)
        # 2026-11-16 or 16/11/2026 (Trinidad writes day first).
        year, month, day = (first, second, third) if first > 31 else (third, second, first)
        if year < 100:
            year += 2000
        try:
            found.add(date(year, month, day))
        except ValueError:
            continue
    months: list[int] = []
    for word in _WORD_RE.findall(text):
        if word in _MONTHS:
            months.append(_MONTHS[word])
        elif len(word) >= 5:
            # "novemer", "febuary": officers type fast on phones.
            close = get_close_matches(word, _FULL_MONTHS, n=1, cutoff=0.8)
            if close:
                months.append(_MONTHS[close[0]])
    days = [int(day) for day in _DAY_RE.findall(text)]
    for month in months:
        for day in days:
            for year in (today.year, today.year - 1):
                try:
                    found.add(date(year, month, day))
                except ValueError:
                    continue
    return found


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def guard_event_dates(
    proposed: CaptureWorkingSet,
    previous: CaptureWorkingSet,
    message: str,
    today: date,
) -> tuple[CaptureWorkingSet, list[str]]:
    """A date may only be set or changed from what this message says.

    Siparia's Nov 16 report was stamped with Oct 4, the date of an earlier,
    different report in the same session."""
    named = dates_in(message, today)
    prior = {row.row_id: row for row in previous.incidents}
    notes: list[str] = []
    rows: list[CaptureIncident] = []
    for row in proposed.incidents:
        before = prior.get(row.row_id)
        old = before.event_date if before is not None else None
        new_date = _iso_date(row.event_date)
        if row.event_date != old and (new_date is None or new_date not in named):
            row = row.model_copy(update={"event_date": old})
            if before is None:
                notes.append(
                    f"I left the date blank on incident {row.row_id}: that message did not say what day it happened."
                )
        rows.append(row)
    return proposed.model_copy(update={"incidents": rows}), notes


def _restore_dropped(kind: str, proposed: list, previous: list) -> tuple[list, list[str]]:
    kept = {row.row_id for row in proposed}
    restored = [row for row in previous if row.row_id not in kept]
    if not restored:
        return proposed, []
    order = {row.row_id: index for index, row in enumerate(previous)}
    merged = sorted(
        [*proposed, *restored],
        key=lambda row: (order.get(row.row_id, len(order)), int(row.row_id) if row.row_id.isdigit() else 0),
    )
    notes = []
    for row in restored:
        label = (
            getattr(row, "incident_summary", None) or getattr(row, "statement", None) or ""
        )
        notes.append(
            f"I kept {kind} {row.row_id}{f' ({label})' if label else ''}. "
            f"Say \"remove {kind} {row.row_id}\" if it should go."
        )
    return merged, notes


def guard_dropped_rows(
    proposed: CaptureWorkingSet, previous: CaptureWorkingSet, message: str
) -> tuple[CaptureWorkingSet, list[str]]:
    """A row disappears only when the officer asks for that.

    Chaguanas' household sandbag request vanished from the logs, and Siparia's
    Fullerton and Woodland disappeared, with no instruction to remove either."""
    if _REMOVAL_RE.search(message):
        return proposed, []
    incidents, incident_notes = _restore_dropped("incident", proposed.incidents, previous.incidents)
    logs, log_notes = _restore_dropped("log", proposed.logs, previous.logs)
    return (
        proposed.model_copy(update={"incidents": incidents, "logs": logs}),
        incident_notes + log_notes,
    )


def release_alert_on_new_level(
    proposed: CaptureWorkingSet, previous: CaptureWorkingSet
) -> CaptureWorkingSet:
    """An officer who reports a new alert in chat is correcting the typed one.

    Point Fortin typed an alert wording early on, then said "Adverse Weather Red
    Level #1"; the typed wording was pinned and the filing read "None". When the
    chat names a different level, the chat's wording replaces the typed one.
    Returns `previous` with the alert wording no longer pinned, for pinning."""
    if "alert_detail" not in previous.manual_fields:
        return previous
    new_level = level_from_alert_detail(proposed.alert_detail) or proposed.alert_level
    if (
        proposed.alert_detail
        and proposed.alert_detail != previous.alert_detail
        and new_level != previous.alert_level
    ):
        return previous.model_copy(
            update={
                "manual_fields": [
                    path for path in previous.manual_fields if path != "alert_detail"
                ]
            }
        )
    return previous


def pinned_field_notes(
    proposed: CaptureWorkingSet, pinned: CaptureWorkingSet
) -> list[str]:
    """Where the model tried to change a hand-typed value and was overruled."""
    notes: list[str] = []
    for name, label in SESSION_LABELS.items():
        if getattr(proposed, name) != getattr(pinned, name):
            value = getattr(pinned, name)
            shown = value.isoformat(sep=" ", timespec="minutes") if isinstance(value, datetime) else value
            notes.append(
                f"{label} was typed in the form, so I kept \"{shown or 'blank'}\". "
                "Change it there if it is out of date."
            )
    proposed_rows = {row.row_id: row for row in proposed.incidents}
    for row in pinned.incidents:
        before = proposed_rows.get(row.row_id)
        if before is None:
            continue
        changed = [
            field
            for field in CaptureIncident.model_fields
            if getattr(before, field) != getattr(row, field)
        ]
        if changed:
            notes.append(
                f"On incident {row.row_id} I kept what was typed in the form for "
                + ", ".join(field.replace("_", " ") for field in changed)
                + "."
            )
    return notes


def echoes_clerk(message: str, history_texts: list[str]) -> bool:
    """The officer pasted a clerk confirmation back as their own report.

    Point Fortin sent "Captured a new flooding incident in Tom Village..." —
    the clerk's own words — to add two details."""
    text = message.strip().lower()
    if _CLAIM_RE.match(text):
        return True
    return any(
        SequenceMatcher(None, text, previous.strip().lower()).ratio() > 0.6
        for previous in history_texts[-6:]
    )


def unchanged_claim_note(assistant: str, changes: list[str]) -> str | None:
    if changes or not _CLAIM_RE.match(assistant or ""):
        return None
    return "Nothing in the report changed from that message."



_ZERO_RE = re.compile(r"\b(0|zero|nil)\b", re.IGNORECASE)


def guard_zero_counts(
    proposed: CaptureWorkingSet, previous: CaptureWorkingSet, message: str
) -> CaptureWorkingSet:
    """"No injuries confirmed" is not a count of zero.

    The model turned "no injuries have been confirmed" into injuries_count 0
    in three UAT sessions. A zero stands only when the officer said 0 or zero;
    otherwise the count stays unknown and injuries_occurred carries the "no"."""
    if _ZERO_RE.search(message):
        return proposed
    prior = {row.row_id: row for row in previous.incidents}
    rows = []
    for row in proposed.incidents:
        before = prior.get(row.row_id)
        update = {}
        for name, occurred in (
            ("injuries_count", "injuries_occurred"),
            ("deaths_count", "deaths_occurred"),
        ):
            if getattr(row, name) == 0 and (before is None or getattr(before, name) != 0):
                # The zero still meant "none happened"; keep that, drop the count.
                update[name] = None
                update[occurred] = False
        rows.append(row.model_copy(update=update) if update else row)
    return proposed.model_copy(update={"incidents": rows})
