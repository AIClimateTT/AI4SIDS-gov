"""How each prompt version behaved on real conversations.

Read from capture_turns, so these are UAT and live turns, not a test set.
Each officer turn records its prompt version, model, whether the reply
parsed, whether it needed a retry, and how many corrections the guards made.
An officer edit right after a turn means the officer fixed something the
clerk captured."""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.capture.models import CaptureTurn

UNRECORDED = "before registry"


@dataclass
class VersionStats:
    prompt_ref: str
    model: str
    turns: int = 0
    sessions: set[int] = field(default_factory=set)
    unreadable: int = 0
    retried: int = 0
    corrected_turns: int = 0
    edited_after: int = 0
    interventions: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def rate(self, count: int) -> str:
        return f"{count / self.turns:.0%}" if self.turns else "—"


def prompt_stats(db: Session, prompt_id: str) -> list[VersionStats]:
    rows = list(
        db.scalars(select(CaptureTurn).order_by(CaptureTurn.session_id, CaptureTurn.seq))
    )
    by_session: dict[int, list[CaptureTurn]] = defaultdict(list)
    for row in rows:
        by_session[row.session_id].append(row)

    groups: dict[tuple[str, str], VersionStats] = {}
    for turns in by_session.values():
        for index, turn in enumerate(turns):
            if turn.kind != "turn":
                continue
            if turn.prompt_id not in (None, prompt_id):
                continue
            ref = f"{prompt_id}@{turn.prompt_version}" if turn.prompt_id else UNRECORDED
            model = turn.model or "unknown"
            stats = groups.setdefault((ref, model), VersionStats(ref, model))
            stats.turns += 1
            stats.sessions.add(turn.session_id)
            if turn.parse_ok is False:
                stats.unreadable += 1
            if turn.retried:
                stats.retried += 1
            corrections = turn.interventions or {}
            if any(corrections.values()):
                stats.corrected_turns += 1
            for name, count in corrections.items():
                stats.interventions[name] += count
            following = turns[index + 1] if index + 1 < len(turns) else None
            if following is not None and following.kind == "edit":
                stats.edited_after += 1

    def order(item: VersionStats) -> tuple[int, str]:
        version = item.prompt_ref.rpartition("@")[2]
        return (int(version) if version.isdigit() else -1, item.model)

    return sorted(groups.values(), key=order)


def stats_lines(stats: list[VersionStats]) -> list[str]:
    if not stats:
        return ["No officer turns recorded yet."]
    lines: list[str] = []
    for item in stats:
        lines += [
            f"{item.prompt_ref} · {item.model}",
            f"  turns {item.turns} across {len(item.sessions)} sessions",
            f"  unreadable reply  {item.rate(item.unreadable)}  ({item.unreadable})",
            f"  needed a retry    {item.rate(item.retried)}  ({item.retried})",
            f"  guards corrected  {item.rate(item.corrected_turns)}  ({item.corrected_turns})",
            f"  officer edited after  {item.rate(item.edited_after)}  ({item.edited_after})",
        ]
        for name, count in sorted(item.interventions.items()):
            lines.append(f"    {name}: {count}")
        lines.append("")
    if any(item.prompt_ref == UNRECORDED for item in stats):
        lines.append(
            f"'{UNRECORDED}': turns recorded before prompt versions were; "
            "guard counts were not kept for them."
        )
    return lines
