"""A capture session as one exportable record: the chat, the working set it
produced, and the sitrep last generated from it. Built for reviewing how
officers talk to the clerk, not for anyone to file from."""

from datetime import datetime, timezone

from app.core.localtime import to_local
from app.core.renderer import strip_citation_markup
from app.modules.capture.diff import working_changes
from app.modules.capture.models import CaptureSession, CaptureTurn
from app.modules.capture.questions import incident_type_display
from app.modules.capture.store import session_missing, working_set_from_session
from app.modules.sitreps.models import Event

TRANSCRIPT_VERSION = 3

_ROLE_LABELS = {"user": "Officer", "assistant": "Clerk"}

_INCIDENT_LABELS = {
    "incident_scope": "Scope",
    "community": "Community",
    "street": "Street",
    "house_number": "House number",
    "incident_type": "Type",
    "raw_incident_type": "Type (as typed)",
    "incident_summary": "Summary",
    "event_date": "Date of event",
    "households_affected": "Households affected",
    "persons_affected": "Persons affected",
    "persons_displaced": "Persons displaced",
    "persons_marooned": "Persons marooned",
    "access_blocked": "Access blocked",
    "injuries_occurred": "Injuries occurred",
    "injuries_count": "Injuries",
    "deaths_occurred": "Deaths occurred",
    "deaths_count": "Deaths",
    "building_damage": "Building damage",
    "special_needs_occupants": "Special needs occupants",
    "estimated_damage_cost": "Estimated damage cost",
    "action_taken": "Action taken",
    "relief_supplied": "Relief supplied",
    "forwarded_to_agency": "Forwarded to agency",
    "further_assessment_required": "Further assessment required",
    "other_follow_up": "Other follow-up",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _local(value: str | datetime | None) -> str:
    """Stored timestamps are UTC; a reviewer reads Trinidad time."""
    if value in (None, ""):
        return "—"
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return to_local(moment).strftime("%Y-%m-%d %H:%M:%S")


def _turns(turns: list[CaptureTurn]) -> list[dict]:
    out: list[dict] = []
    previous: dict | None = None
    for turn in turns:
        out.append(
            {
                "seq": turn.seq,
                "kind": turn.kind,
                "created_at": _iso(turn.created_at),
                "user_message": turn.user_message,
                "assistant_message": turn.assistant_message,
                "parse_ok": turn.parse_ok,
                "raw_output": turn.raw_output,
                "template_version": turn.template_version,
                "prompt": (
                    f"{turn.prompt_id}@{turn.prompt_version}" if turn.prompt_id else None
                ),
                "prompt_hash": turn.prompt_hash,
                "model": turn.model,
                "retried": turn.retried,
                "interventions": turn.interventions or {},
                "changes": working_changes(previous, turn.working),
                "working": turn.working,
                "missing": turn.missing,
                "sitrep_markdown": turn.sitrep_markdown,
            }
        )
        previous = turn.working
    return out


def _sitrep(row: CaptureSession) -> dict | None:
    if row.sitrep_markdown is None or row.sitrep_generated_at is None:
        return None
    source = row.sitrep_source_updated_at
    return {
        "status": row.sitrep_status,
        "generated_at": _iso(row.sitrep_generated_at),
        "source_updated_at": _iso(source),
        # The working set moved on after this sitrep was generated.
        "stale": source is None or source < row.updated_at,
        "final_markdown": strip_citation_markup(
            row.sitrep_final_markdown or row.sitrep_markdown
        ),
        "draft_markdown": row.sitrep_markdown,
        "fact_table": row.sitrep_fact_table or {},
        "violations": row.sitrep_violations or [],
    }


def build_transcript(
    row: CaptureSession, event: Event | None, turns: list[CaptureTurn] | None = None
) -> dict:
    working = working_set_from_session(row)
    return {
        "transcript_version": TRANSCRIPT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session": {
            "id": row.id,
            "corporation": row.corporation,
            "status": row.status,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
            "submission_id": row.submission_id,
            "report_id": row.report_id,
        },
        "event": (
            {
                "id": event.id,
                "title": event.title,
                "hazard_type": event.hazard_type,
                "started_at": _iso(event.started_at),
                "ended_at": _iso(event.ended_at),
            }
            if event is not None
            else None
        ),
        "messages": list(row.messages or []),
        "capture": working.model_dump(mode="json"),
        "missing": [item.model_dump() for item in session_missing(row)],
        "sitrep": _sitrep(row),
        # Snapshots exist only for changes made after they were introduced.
        "turns": _turns(turns or []),
    }


def _value(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _display(key: str, value: object) -> object:
    if key == "incident_type" and isinstance(value, str):
        return incident_type_display(value)
    return value


def _line(label: str, value: object) -> str:
    return f"- **{label}:** {_value(value) if value not in (None, '') else '—'}"


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def transcript_markdown(data: dict) -> str:
    session = data["session"]
    event = data["event"]
    capture = data["capture"]
    out: list[str] = [
        f"# Capture transcript: {session['corporation']}, session {session['id']}",
        "",
        _line("Status", session["status"]),
        _line(
            "Event",
            f"{event['title']} ({event['hazard_type']})" if event else None,
        ),
        _line("Opened", _local(session["created_at"])),
        _line("Last activity", _local(session["updated_at"])),
        _line("Submission", session["submission_id"]),
        _line("Report", session["report_id"]),
        _line("Exported", _local(data["exported_at"])),
        "",
        "Times are Trinidad local time.",
        "",
        "## Conversation",
        "",
    ]
    for message in data["messages"]:
        role = _ROLE_LABELS.get(message.get("role", ""), message.get("role", ""))
        out += [f"**{role}** · {_local(message.get('created_at'))}", "", _quote(message.get("content", "")), ""]

    manual = set(capture.get("manual_fields") or [])
    out += [
        "## Captured facts",
        "",
        _line("As at", capture.get("as_at")),
        _line("Alert level", capture.get("alert_level")),
        _line("Alert detail", capture.get("alert_detail")),
        _line("Present activity", capture.get("present_activity")),
        _line("Situation overview", capture.get("situation_overview")),
        _line("Typed by the officer", ", ".join(sorted(manual)) or None),
        "",
    ]

    incidents = capture.get("incidents") or []
    out += [f"## Incidents ({len(incidents)})", ""]
    for incident in incidents:
        out.append(f"### Row {incident.get('row_id') or '?'}")
        out += [
            _line(label, _display(key, incident.get(key)))
            for key, label in _INCIDENT_LABELS.items()
            if incident.get(key) not in (None, "")
        ]
        out.append("")

    logs = capture.get("logs") or []
    out += [f"## Situation logs ({len(logs)})", ""]
    for log in logs:
        amount = " ".join(
            _value(part) for part in (log.get("quantity"), log.get("unit")) if part is not None
        )
        extras = ", ".join(
            part for part in (log.get("item"), amount, log.get("status")) if part
        )
        out.append(
            f"- [{log.get('category')}] {log.get('statement')}"
            + (f" ({extras})" if extras else "")
        )
    out.append("")

    missing = data["missing"]
    out += ["## Still missing", ""]
    out += [f"- {item['message']} (`{item['path']}`)" for item in missing] or ["- Nothing"]
    out.append("")

    sitrep = data["sitrep"]
    out += ["## Generated sitrep", ""]
    if sitrep is None:
        out += ["No sitrep has been generated from this session.", ""]
    else:
        out += [
            _line("Status", sitrep["status"]),
            _line("Generated", _local(sitrep["generated_at"])),
            _line(
                "Matches the working set",
                "no, the conversation continued after it was generated"
                if sitrep["stale"]
                else "yes",
            ),
            _line("Citation violations", len(sitrep["violations"])),
            "",
            "---",
            "",
            sitrep["final_markdown"].strip(),
            "",
        ]
    out += _turns_markdown(data.get("turns") or [])
    return "\n".join(out)


def _turns_markdown(turns: list[dict]) -> list[str]:
    out = ["", "## Turn by turn", ""]
    if not turns:
        return out + [
            "No snapshots. This session's changes predate per-turn recording.",
            "",
        ]
    for turn in turns:
        flag = " · **model output unreadable**" if turn["parse_ok"] is False else ""
        if turn.get("prompt"):
            version = f" · {turn['prompt']} · {turn.get('model') or 'model unknown'}"
        elif turn["template_version"]:
            version = f" · template v{turn['template_version']}"
        else:
            version = ""
        out += [f"### {turn['seq']}. {turn['kind']} · {_local(turn['created_at'])}{version}{flag}", ""]
        if turn["user_message"]:
            out += [_quote(turn["user_message"]), ""]
        if turn["assistant_message"]:
            out += [f"Clerk: {turn['assistant_message']}", ""]
        changes = turn["changes"]
        out += [f"- {line}" for line in changes] or ["- No change to the working set"]
        out.append("")
        corrections = turn.get("interventions") or {}
        if corrections or turn.get("retried"):
            parts = [f"{name.replace('_', ' ')} {count}" for name, count in sorted(corrections.items())]
            if turn.get("retried"):
                parts.insert(0, "retried once")
            out += [f"Corrections to the model's reply: {', '.join(parts)}", ""]
        if turn["parse_ok"] is False and turn["raw_output"]:
            out += ["Raw model output:", "", "```", turn["raw_output"], "```", ""]
        if turn["sitrep_markdown"]:
            out += [
                "<details><summary>Sitrep at this point</summary>",
                "",
                turn["sitrep_markdown"].strip(),
                "",
                "</details>",
                "",
            ]
    return out
