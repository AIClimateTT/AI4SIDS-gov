"""Replay recorded capture chats against prompt versions.

For checking a reported issue or a complaint of drift on the real chat
instead of a hand-written case: read a session's officer turns from the
staging or prod database, run each turn again with one or more prompt
versions (or an uncommitted draft) on today's model, and show what each
produced next to what was recorded.

Two modes:
  recorded  each turn starts from the working set and chat history as they
            were recorded, so every turn is judged on exactly the situation
            the officer saw. Differences do not compound. The default.
  chained   the whole chat runs again from its first message, each turn on
            top of the replay's own previous result: what the officer would
            have ended with on that version.

A replay has no checks and no pass rate: nothing in the database says what
the right capture was. It shows differences; a person decides which is
right. A chat that shows a real bug is written up as a case in cases.yaml
(with made-up names and addresses) so it is scored on every version after.

Sources are read-only: the runner opens them with a read-only transaction
default, and the connection URL should use a read-only role as well. Replay
results hold real officer messages, so they stay in the runner's volume and,
when fetched to a laptop, in the git-ignored evals/replays/."""

import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from functools import cache

from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.llm import LLMClient, model_label
from app.core.localtime import local_date, to_local
from app.modules.capture.diff import working_changes
from app.modules.capture.models import CaptureSession, CaptureTurn
from app.modules.capture.schemas import CaptureMessage, CaptureWorkingSet
from app.modules.capture.turn import run_turn
from app.prompts.registry import Prompt

MODES = ("recorded", "chained")
MAX_MODEL_CALLS = 60


# --- sources --------------------------------------------------------------------


def source_urls() -> dict[str, str]:
    urls = {
        "staging": settings.eval_staging_database_url,
        "prod": settings.eval_prod_database_url,
    }
    return {name: url for name, url in urls.items() if url}


def read_only_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_read_only(dbapi_connection, _record) -> None:
            dbapi_connection.execute("PRAGMA query_only = ON")

        return engine
    return create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


@cache
def _engine(source: str) -> Engine:
    return read_only_engine(source_urls()[source])


def open_source(source: str) -> Session:
    if source not in source_urls():
        raise KeyError(source)
    return Session(_engine(source))


# --- listing --------------------------------------------------------------------


def _local(value: datetime | None) -> str | None:
    return to_local(value).isoformat(timespec="minutes") if value else None


def _first_message(row: CaptureSession, limit: int = 80) -> str:
    for message in row.messages or []:
        if message.get("role") == "user":
            text = " ".join(str(message.get("content", "")).split())
            return text if len(text) <= limit else text[: limit - 1] + "…"
    return ""


def list_sessions(
    db: Session,
    corporation: str | None = None,
    since: date | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Capture sessions, most recently changed first, dated in local time."""
    query = select(CaptureSession).order_by(CaptureSession.updated_at.desc()).limit(limit)
    if corporation:
        query = query.where(CaptureSession.corporation.ilike(f"%{corporation}%"))
    if since:
        query = query.where(CaptureSession.updated_at >= datetime(since.year, since.month, since.day))
    if status:
        query = query.where(CaptureSession.status == status)
    rows = db.scalars(query).all()
    if not rows:
        return []
    ids = [row.id for row in rows]
    turn_counts = dict(
        db.execute(
            select(CaptureTurn.session_id, func.count())
            .where(CaptureTurn.session_id.in_(ids), CaptureTurn.kind == "turn")
            .group_by(CaptureTurn.session_id)
        ).all()
    )
    prompts: dict[int, set[str]] = {}
    for session_id, prompt_id, version in db.execute(
        select(CaptureTurn.session_id, CaptureTurn.prompt_id, CaptureTurn.prompt_version)
        .where(CaptureTurn.session_id.in_(ids), CaptureTurn.kind == "turn")
        .distinct()
    ).all():
        prompts.setdefault(session_id, set()).add(
            f"{prompt_id}@{version}" if prompt_id else "before registry"
        )
    return [
        {
            "id": row.id,
            "corporation": row.corporation,
            "status": row.status,
            "filed": row.submission_id is not None,
            "event_id": row.event_id,
            "created_at": _local(row.created_at),
            "updated_at": _local(row.updated_at),
            "officer_turns": turn_counts.get(row.id, 0),
            "incidents": len(row.incidents or []),
            "logs": len(row.logs or []),
            "prompts": sorted(prompts.get(row.id, set())),
            "first_message": _first_message(row),
        }
        for row in rows
    ]


def session_detail(db: Session, session_id: int) -> dict | None:
    row = db.get(CaptureSession, session_id)
    if row is None:
        return None
    turns = db.scalars(
        select(CaptureTurn).where(CaptureTurn.session_id == session_id).order_by(CaptureTurn.seq)
    ).all()
    return {
        "id": row.id,
        "corporation": row.corporation,
        "status": row.status,
        "filed": row.submission_id is not None,
        "created_at": _local(row.created_at),
        "updated_at": _local(row.updated_at),
        "turns": [
            {
                "seq": turn.seq,
                "kind": turn.kind,
                "at": _local(turn.created_at),
                "prompt": f"{turn.prompt_id}@{turn.prompt_version}" if turn.prompt_id else None,
                "model": turn.model,
                "parse_ok": turn.parse_ok,
                "interventions": turn.interventions or {},
                "user_message": turn.user_message,
            }
            for turn in turns
        ],
    }


# --- recorded turns -------------------------------------------------------------


@dataclass
class RecordedTurn:
    seq: int
    today: date
    message: str
    before: dict
    after: dict
    history: list[dict]
    assistant_message: str
    prompt: str | None
    model: str | None
    interventions: dict = field(default_factory=dict)


def recorded_turns(db: Session, session_id: int) -> list[RecordedTurn]:
    """Each officer turn with the working set and chat it started from."""
    row = db.get(CaptureSession, session_id)
    if row is None:
        raise KeyError(session_id)
    turns = db.scalars(
        select(CaptureTurn).where(CaptureTurn.session_id == session_id).order_by(CaptureTurn.seq)
    ).all()
    messages = list(row.messages or [])
    cursor = 0
    previous: dict = {}
    out: list[RecordedTurn] = []
    for turn in turns:
        if turn.kind == "turn" and turn.user_message:
            text = turn.user_message.strip()
            # The officer's message in the stored chat, in order; the chat
            # before it is what the model saw.
            index = next(
                (
                    i
                    for i in range(cursor, len(messages))
                    if messages[i].get("role") == "user" and str(messages[i].get("content", "")).strip() == text
                ),
                None,
            )
            if index is None:
                index = next(
                    (i for i in range(cursor, len(messages)) if messages[i].get("role") == "user"),
                    len(messages),
                )
            history = messages[:index]
            cursor = index + 1
            out.append(
                RecordedTurn(
                    seq=turn.seq,
                    today=local_date(turn.created_at),
                    message=text,
                    before=previous,
                    after=turn.working,
                    history=history,
                    assistant_message=turn.assistant_message or "",
                    prompt=f"{turn.prompt_id}@{turn.prompt_version}" if turn.prompt_id else None,
                    model=turn.model,
                    interventions=turn.interventions or {},
                )
            )
        previous = turn.working
    return out


# --- replay -------------------------------------------------------------------


@dataclass
class ReplayedTurn:
    parse_ok: bool
    seconds: float
    assistant_message: str
    questions: list[str]
    interventions: dict[str, int]
    changes: list[str]
    vs_recorded: list[str]
    working: dict
    error: str | None = None


def _diff(before: dict, after: dict) -> list[str]:
    """working_changes without as_at: the session's clock, not a capture decision."""
    return working_changes(
        {k: v for k, v in before.items() if k != "as_at"},
        {k: v for k, v in after.items() if k != "as_at"},
    )


def _messages(history: list[dict] | list[CaptureMessage]) -> list[CaptureMessage]:
    return [
        item if isinstance(item, CaptureMessage) else CaptureMessage.model_validate(item)
        for item in history
    ]


def replay_session(
    turns: list[RecordedTurn],
    prompts: list[Prompt],
    llm: LLMClient,
    mode: str = "recorded",
    progress=None,
) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    by_prompt: dict[str, list[ReplayedTurn]] = {}
    for prompt in prompts:
        runs: list[ReplayedTurn] = []
        working = CaptureWorkingSet.model_validate(turns[0].before) if turns else CaptureWorkingSet()
        history = _messages(turns[0].history) if turns else []
        for turn in turns:
            if mode == "recorded":
                working = CaptureWorkingSet.model_validate(turn.before)
                history = _messages(turn.history)
            before = working.model_dump(mode="json")
            started = time.monotonic()
            try:
                done = run_turn(
                    working, history, turn.message, llm, system_prompt=prompt.text, today=turn.today
                )
            except Exception as exc:  # noqa: BLE001 - a model failure fails the turn, not the replay
                runs.append(
                    ReplayedTurn(False, round(time.monotonic() - started, 2), "", [], {}, [], [], {},
                                 error=f"{type(exc).__name__}: {exc}")
                )
                if progress:
                    progress(f"{prompt.ref} turn {turn.seq}: failed")
                continue
            out = done.working.model_dump(mode="json")
            runs.append(
                ReplayedTurn(
                    parse_ok=done.parse_ok,
                    seconds=round(time.monotonic() - started, 2),
                    assistant_message=done.assistant_message,
                    questions=done.questions,
                    interventions=done.interventions,
                    changes=_diff(before, out),
                    vs_recorded=_diff(turn.after, out),
                    working=out,
                )
            )
            if mode == "chained":
                working, history = done.working, done.messages
            if progress:
                progress(f"{prompt.ref} turn {turn.seq}: {len(runs[-1].vs_recorded)} differences from recorded")
        by_prompt[prompt.ref] = runs

    refs = [prompt.ref for prompt in prompts]
    rows = []
    for i, turn in enumerate(turns):
        replays = {ref: asdict(by_prompt[ref][i]) for ref in refs}
        if len(refs) > 1:
            first = by_prompt[refs[0]][i].working
            for ref in refs[1:]:
                replays[ref]["vs_" + refs[0]] = _diff(first, by_prompt[ref][i].working)
        rows.append(
            {
                "seq": turn.seq,
                "today": turn.today.isoformat(),
                "message": turn.message,
                "recorded": {
                    "prompt": turn.prompt,
                    "model": turn.model,
                    "assistant_message": turn.assistant_message,
                    "interventions": turn.interventions,
                    "changes": _diff(turn.before, turn.after),
                },
                "replays": replays,
            }
        )
    return {
        "kind": "replay",
        "mode": mode,
        "model": model_label(llm),
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "prompts": [{"ref": prompt.ref, "hash": prompt.hash} for prompt in prompts],
        "turns": rows,
        "summary": summarize_replay(by_prompt),
    }


def summarize_replay(by_prompt: dict[str, list[ReplayedTurn]]) -> dict:
    summary = {}
    for ref, runs in by_prompt.items():
        interventions: dict[str, int] = {}
        for run in runs:
            for key, count in run.interventions.items():
                interventions[key] = interventions.get(key, 0) + count
        summary[ref] = {
            "turns": len(runs),
            "unreadable": sum(not run.parse_ok for run in runs),
            "failed": sum(run.error is not None for run in runs),
            "differ_from_recorded": sum(bool(run.vs_recorded) for run in runs),
            "interventions": interventions,
        }
    return summary


def replay_lines(result: dict) -> list[str]:
    """Readable report: per turn, what was recorded and what each version did."""
    source = f"{result.get('source', '?')} session {result.get('session_id', '?')}"
    lines = [
        f"replay of {source} ({result.get('corporation', '')}), {result['mode']} mode, {result['model']}",
        "",
    ]
    for ref, stats in result["summary"].items():
        corrections = ", ".join(f"{k} {v}" for k, v in sorted(stats["interventions"].items())) or "none"
        lines.append(
            f"{ref}: {stats['differ_from_recorded']}/{stats['turns']} turns differ from recorded, "
            f"{stats['unreadable']} unreadable, {stats['failed']} failed; corrections: {corrections}"
        )
    for turn in result["turns"]:
        lines += ["", f"--- turn {turn['seq']} ({turn['today']}): {turn['message']}"]
        recorded = turn["recorded"]
        lines.append(f"  recorded ({recorded['prompt'] or 'before registry'}): {recorded['assistant_message']}")
        for change in recorded["changes"]:
            lines.append(f"    {change}")
        for ref, run in turn["replays"].items():
            if run.get("error"):
                lines.append(f"  {ref}: failed: {run['error']}")
                continue
            lines.append(f"  {ref}: {run['assistant_message']}")
            for question in run["questions"]:
                lines.append(f"    asks: {question}")
            if run["interventions"]:
                lines.append(f"    corrections: {run['interventions']}")
            label = "vs recorded" if result["mode"] == "recorded" else "vs recorded (chained)"
            if run["vs_recorded"]:
                lines.append(f"    {label}:")
                lines += [f"      {change}" for change in run["vs_recorded"]]
            else:
                lines.append(f"    {label}: same")
            for key, changes in run.items():
                if key.startswith("vs_") and key != "vs_recorded" and changes:
                    lines.append(f"    {key.replace('_', ' ')}:")
                    lines += [f"      {change}" for change in changes]
    return lines
