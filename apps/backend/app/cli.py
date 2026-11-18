import re
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.template_catalog import get_template, list_templates
from app.db import Base, SessionLocal, engine
from app.config import settings
from app.modules.survey123.client import (
    Survey123NotConfigured,
    Survey123Unavailable,
    query_responses,
)
from app.modules.survey123.ingest import IngestFormatError, ingest_survey123_export
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS, CORPORATION_LABELS
from app.modules.survey123.pull import pull_survey123
from app.templates.loader import load_template

app = typer.Typer()
ingest_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("survey123")
def ingest_survey123(file_path: Path) -> None:
    session = SessionLocal()
    try:
        result = ingest_survey123_export(file_path, session, settings.dedup_salt)
    except IngestFormatError as exc:
        typer.echo(exc.detail, err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"duplicates_flagged={result.duplicates_flagged}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    typer.echo(f"pii_columns_dropped={result.pii_columns_dropped}")


@app.command("submissions")
def create_submission_command(
    corporation: str,
    as_at: str,
    incidents: Optional[Path] = None,
    logs: Optional[Path] = None,
    event_id: Optional[int] = None,
    alert_level: str = "none",
) -> None:
    from datetime import datetime

    from app.db import SessionLocal
    from app.modules.sitreps.ingest import ingest_submission

    if corporation not in CANONICAL_CORPORATIONS:
        typer.echo(f"unknown corporation: {corporation}", err=True)
        raise typer.Exit(code=1)

    if incidents is not None and event_id is None:
        typer.echo(
            "a submission carrying incidents must name an event; pass --event-id",
            err=True,
        )
        raise typer.Exit(code=1)

    # Record just the filename, not the full local path: the path is an
    # artifact of whatever machine ran the CLI, not part of the corp's
    # submission. This also keeps source_file's format consistent with the
    # API, which records the uploaded filename the same way.
    source_name = ",".join(p.name for p in (incidents, logs) if p is not None) or None

    session = SessionLocal()
    try:
        result = ingest_submission(
            session,
            corporation=corporation,
            as_at=datetime.fromisoformat(as_at),
            event_id=event_id,
            alert_level=alert_level,
            incidents_path=incidents,
            logs_path=logs,
            source_name=source_name,
        )
    finally:
        session.close()

    typer.echo(result.model_dump_json(indent=2))


@app.command("withdraw-submission")
def withdraw_submission_command(
    submission_id: int,
    yes: bool = typer.Option(False, "--yes", help="Delete; without it, only show the plan"),
) -> None:
    """Remove a filing that should never have reached the register (e.g. test data).

    Deletes its incidents, logs and issued report. The capture session is kept,
    marked withdrawn, so its transcript can still be exported."""
    from app.core import report_models  # noqa: F401
    from app.modules.capture import models as capture_models  # noqa: F401
    from app.modules.sitreps.withdraw import plan_withdrawal, withdraw_submission
    from app.quality import models as quality_models  # noqa: F401

    session = SessionLocal()
    try:
        plan = plan_withdrawal(session, submission_id)
        if plan is None:
            typer.echo(f"submission not found: {submission_id}", err=True)
            raise typer.Exit(code=1)
        target = engine.url.render_as_string(hide_password=True)
        typer.echo(f"database: {target}")
        for line in plan.lines():
            typer.echo(line)
        if not yes:
            typer.echo("dry run: nothing deleted. Re-run with --yes to withdraw.")
            return
        withdraw_submission(session, plan)
        typer.echo(f"withdrew submission {submission_id}")
    finally:
        session.close()


@app.command("list-templates")
def list_templates_command() -> None:
    for template in list_templates():
        typer.echo(f"{template.name} (v{template.version}): {template.title}")


@app.command()
def generate(
    template_name: str,
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
    corporation: str = typer.Option(None, "--corporation"),
    community: str = typer.Option(None, "--community"),
) -> None:
    # A corporation that is not one of the fourteen matches no row, and every
    # metric reports a confident zero for it. Rejected before any query runs,
    # exactly as POST /reports does.
    if corporation is not None and corporation not in CANONICAL_CORPORATIONS:
        typer.echo(f"unknown corporation: {corporation}", err=True)
        raise typer.Exit(code=1)

    session = SessionLocal()
    try:
        template = get_template(template_name)
        if template is None:
            typer.echo(f"unknown template: {template_name}", err=True)
            raise typer.Exit(code=1)
        if template_name == "corp_situation_report":
            typer.echo(
                "corp sitreps are issued from capture, not generated here",
                err=True,
            )
            raise typer.Exit(code=1)

        params = {
            "date_from": date_from,
            "date_to": date_to,
            "corporation": corporation,
            "community": community,
        }

        try:
            report = generate_report(template, params, session, get_default_llm_client())
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    finally:
        session.close()

    typer.echo(report.markdown)
    typer.echo(f"status: {report.status}", err=True)
    if report.violations:
        typer.echo(f"violations: {len(report.violations)}", err=True)


@app.command("quality-rescore")
def quality_rescore() -> None:
    from app.core.citation_check import check_citations
    from app.core.contracts import FactTable
    from app.core.report_models import Report
    from app.quality.score import score_quality

    session = SessionLocal()
    try:
        rows = list(session.query(Report).all())
        updated = 0
        skipped = 0
        for row in rows:
            if not row.narrative:
                skipped += 1
                continue
            template = get_template(row.template)
            if template is None:
                skipped += 1
                continue
            fact_table = FactTable.model_validate(row.fact_table)
            result = check_citations(row.narrative, fact_table)
            eval_ = score_quality(
                template, fact_table, row.narrative, row.markdown, result
            )
            row.quality_eval = eval_.model_dump(mode="json")
            updated += 1
        session.commit()
        typer.echo(f"rescored={updated} skipped={skipped}")
    finally:
        session.close()


users_app = typer.Typer()
app.add_typer(users_app, name="users")


@users_app.command("create")
def create_user_command(
    email: str,
    role: str = typer.Option(..., "--role", help="dmu, admin, or corp"),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
    first_name: str | None = None,
    last_name: str | None = None,
    corporation: str | None = None,
) -> None:
    from app.auth.models import User
    from app.auth.passwords import hash_password

    allowed = {"dmu", "admin", "corp"}
    if role not in allowed:
        typer.echo(f"role must be one of: {', '.join(sorted(allowed))}", err=True)
        raise typer.Exit(code=1)
    if role == "corp" and not corporation:
        typer.echo("corp users require --corporation", err=True)
        raise typer.Exit(code=1)
    if role == "corp" and corporation not in CANONICAL_CORPORATIONS:
        typer.echo(f"unknown corporation: {corporation}", err=True)
        raise typer.Exit(code=1)
    if role != "corp":
        corporation = None
    if len(password) < 8:
        typer.echo("password must be at least 8 characters", err=True)
        raise typer.Exit(code=1)

    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email == email.lower().strip()).one_or_none()
        if existing is not None:
            typer.echo(f"user already exists: {existing.email}", err=True)
            raise typer.Exit(code=1)
        user = User(
            email=email.lower().strip(),
            role=role,
            first_name=first_name,
            last_name=last_name,
            corporation=corporation,
            is_active=True,
            password_hash=hash_password(password),
        )
        session.add(user)
        session.commit()
        typer.echo(f"created {user.email} role={user.role} id={user.user_id}")
    finally:
        session.close()


@users_app.command("set-password")
def set_password_command(
    email: str,
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
) -> None:
    from app.auth.models import User
    from app.auth.passwords import hash_password

    if len(password) < 8:
        typer.echo("password must be at least 8 characters", err=True)
        raise typer.Exit(code=1)

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == email.lower().strip()).one_or_none()
        if user is None:
            typer.echo(f"user not found: {email}", err=True)
            raise typer.Exit(code=1)
        user.password_hash = hash_password(password)
        session.commit()
        typer.echo(f"updated password for {user.email}")
    finally:
        session.close()


db_app = typer.Typer()
app.add_typer(db_app, name="db")

SEED_PASSWORD = "Password123!"

# (email, first_name, last_name), all seeded as admins.
SEED_ADMINS = [
    ("murraydevon14@gmail.com", "Devon", "Murray - Developer"),
    ("latoyapaul2508@gmail.com", "Latoya", "Paul - Developer"),
    ("dmu_admin@mail.com", "DMU", "Admin"),
    ("nivan.moonsammy@gov.tt", "Nivan", "Moonsammy"),
]


def _seed_corp_place(label: str) -> str:
    # "San Juan/Laventille Regional Corporation" -> "San Juan/Laventille"
    return re.sub(r" (Regional|City|Borough) Corporation$", "", label)


def _seed_corp_email(label: str) -> str:
    # "San Juan/Laventille Regional Corporation" -> sanjuancorp@mail.com
    first_place = _seed_corp_place(label).split("/")[0]
    return f"{first_place.replace(' ', '').lower()}corp@mail.com"


def _clear_tables(session: Session) -> None:
    # alembic_version is not in the metadata, so the schema stays at head.
    # prompt_versions is history of what models were told, not test data.
    tables = [t for t in Base.metadata.sorted_tables if t.name != "prompt_versions"]
    if session.get_bind().dialect.name == "postgresql":
        names = [table.name for table in tables]
        # Queued jobs point at reports that are about to disappear.
        if inspect(session.connection()).has_table("procrastinate_jobs"):
            names.append("procrastinate_jobs")
        session.execute(text(f"TRUNCATE {', '.join(names)} RESTART IDENTITY CASCADE"))
        return
    for table in reversed(tables):
        session.execute(table.delete())


@db_app.command("reset")
def reset_db_command(
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt"),
) -> None:
    """Erase all data, then seed the admins and one account per corporation."""
    from app.auth import models as auth_models
    from app.auth.passwords import hash_password
    from app.core import report_models  # noqa: F401
    from app.modules.capture import models as capture_models  # noqa: F401
    from app.modules.sitreps import models as sitreps_models  # noqa: F401
    from app.modules.survey123 import models as survey123_models  # noqa: F401
    from app.quality import models as quality_models  # noqa: F401

    target = engine.url.render_as_string(hide_password=True)
    if not yes:
        typer.confirm(f"Erase all data in {target}?", abort=True)

    session = SessionLocal()
    try:
        _clear_tables(session)
        for email, first_name, last_name in SEED_ADMINS:
            session.add(
                auth_models.User(
                    email=email,
                    role="admin",
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                    password_hash=hash_password(SEED_PASSWORD),
                )
            )
        for corporation, label in sorted(CORPORATION_LABELS.items()):
            session.add(
                auth_models.User(
                    email=_seed_corp_email(label),
                    role="corp",
                    first_name=_seed_corp_place(label),
                    last_name="Corporation",
                    corporation=corporation,
                    is_active=True,
                    password_hash=hash_password(SEED_PASSWORD),
                )
            )
        session.commit()
    finally:
        session.close()

    typer.echo(f"reset {target}")
    for email, _, _ in SEED_ADMINS:
        typer.echo(f"admin: {email}")
    for corporation, label in sorted(CORPORATION_LABELS.items()):
        typer.echo(f"corp: {_seed_corp_email(label)} ({corporation})")


prompts_app = typer.Typer(help="Versioned model prompts (app/prompts).")
app.add_typer(prompts_app, name="prompts")


@prompts_app.command("list")
def prompts_list_command() -> None:
    from app.prompts.registry import assemble, load_spec, prompt_ids

    for prompt_id in prompt_ids():
        spec, prompt = load_spec(prompt_id), assemble(prompt_id)
        typer.echo(f"{prompt.ref}  {prompt.hash[:12]}  {spec.description}")


@prompts_app.command("show")
def prompts_show_command(prompt_id: str) -> None:
    """Print the prompt exactly as the model receives it."""
    from app.prompts.registry import assemble

    typer.echo(assemble(prompt_id).text)


@prompts_app.command("check")
def prompts_check_command() -> None:
    """Fail if a prompt changed without a version bump and changelog entry."""
    from app.prompts.registry import lock_problems

    problems = lock_problems()
    for problem in problems:
        typer.echo(problem, err=True)
    if problems:
        raise typer.Exit(code=1)
    typer.echo("prompts match prompts.lock.json")


@prompts_app.command("lock")
def prompts_lock_command() -> None:
    """Record new prompt versions in prompts.lock.json."""
    from app.prompts.registry import write_lock

    try:
        added = write_lock()
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"locked: {', '.join(added)}" if added else "nothing new to lock")


@prompts_app.command("stats")
def prompts_stats_command(prompt_id: str = "corp_capture") -> None:
    """How each version of a prompt behaved on recorded conversations."""
    from app.prompts.stats import prompt_stats, stats_lines

    session = SessionLocal()
    try:
        for line in stats_lines(prompt_stats(session, prompt_id)):
            typer.echo(line)
    finally:
        session.close()


@prompts_app.command("eval")
def prompts_eval_command(
    prompt_id: str = typer.Argument("corp_capture"),
    version: Optional[int] = typer.Option(None, help="An earlier, frozen version; default current"),
    repeat: int = typer.Option(3, help="Runs per case; models vary run to run"),
    case: Optional[list[str]] = typer.Option(None, help="Only these case ids"),
    out: Optional[Path] = typer.Option(None, help="Results folder; default evals/<id>/results"),
) -> None:
    """Score a prompt version on the test set with the configured chat model."""
    from app.core.llm import get_llm_client
    from app.prompts.evals import EVALS_DIR, load_cases, run_eval, save_result, summary_lines
    from app.prompts.registry import load_version

    prompt = load_version(prompt_id, version)
    cases = load_cases(prompt_id)
    if case:
        cases = [item for item in cases if item.id in set(case)]
    result = run_eval(prompt, get_llm_client("chat"), cases, repeat=repeat, progress=typer.echo)
    path = save_result(result, out or EVALS_DIR / prompt_id / "results")
    typer.echo("")
    for line in summary_lines(result):
        typer.echo(line)
    typer.echo(f"saved {path}")


@prompts_app.command("compare")
def prompts_compare_command(before: Path, after: Path) -> None:
    """What changed between two eval results (e.g. v1 and v2 on the same model)."""
    import json as _json

    from app.prompts.evals import compare_lines

    for line in compare_lines(
        _json.loads(before.read_text(encoding="utf-8")),
        _json.loads(after.read_text(encoding="utf-8")),
    ):
        typer.echo(line)


def _runner():
    """httpx client for the prod eval runner, from EVAL_RUNNER_URL / _API_KEY
    (environment or apps/backend/.env)."""
    import httpx

    if not settings.eval_runner_url or not settings.eval_runner_api_key:
        typer.echo("Set EVAL_RUNNER_URL and EVAL_RUNNER_API_KEY (env or apps/backend/.env).", err=True)
        raise typer.Exit(code=2)
    return httpx.Client(
        base_url=settings.eval_runner_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.eval_runner_api_key}"},
        timeout=60,
    )


def _runner_get(client, path: str, **params):
    response = client.get(path, params=params or None)
    if response.status_code >= 400:
        typer.echo(f"{response.status_code}: {response.text}", err=True)
        raise typer.Exit(code=1)
    return response.json()


@prompts_app.command("remote-info")
def prompts_remote_info_command() -> None:
    """Which prompt versions and model the prod eval runner has deployed."""
    with _runner() as client:
        data = _runner_get(client, "/info")
    typer.echo(f"model: {data['model']}")
    for prompt in data["prompts"]:
        typer.echo(f"{prompt['id']}@{prompt['version']}  {prompt['hash'][:12]}")


@prompts_app.command("remote-eval")
def prompts_remote_eval_command(
    prompt_id: str = typer.Argument("corp_capture"),
    version: Optional[int] = typer.Option(None, help="An earlier, frozen version; default current"),
    repeat: int = typer.Option(3, help="Runs per case (1-5)"),
    case: Optional[list[str]] = typer.Option(None, help="Only these case ids"),
    wait: bool = typer.Option(True, help="Wait for the result and save it locally"),
) -> None:
    """Run the test set in prod against NIM; save the result in evals/<id>/results."""
    import time

    from app.prompts.evals import EVALS_DIR, summary_lines

    with _runner() as client:
        response = client.post(
            "/evals",
            json={"prompt_id": prompt_id, "version": version, "repeat": repeat, "cases": case or None},
        )
        if response.status_code >= 400:
            typer.echo(f"{response.status_code}: {response.text}", err=True)
            raise typer.Exit(code=1)
        started = response.json()
        run_id = started["id"]
        from app.prompts.registry import load_version

        try:
            local_hash = load_version(prompt_id, version).hash
        except ValueError:
            local_hash = None
        typer.echo(f"started {run_id}: {started['total']} turns ({started['prompt_hash'][:12]})")
        if local_hash and local_hash != started["prompt_hash"]:
            typer.echo(
                "warning: prod has a different text for this version than this checkout; "
                "push and let it redeploy first",
                err=True,
            )
        if not wait:
            typer.echo(f"fetch later: python -m app.cli prompts remote-result {run_id}")
            return
        seen = 0
        while True:
            state = _runner_get(client, f"/evals/{run_id}")
            for line in state.get("log", [])[seen:]:
                typer.echo(f"  {line}")
            seen = len(state.get("log", [])) or seen
            if state["status"] != "running":
                break
            time.sleep(10)
    _save_remote(state, EVALS_DIR / prompt_id / "results", summary_lines)


def _save_remote(state: dict, out_dir: Path, summary_lines) -> None:
    if state["status"] == "failed":
        typer.echo(f"run failed: {state.get('error')}", err=True)
        raise typer.Exit(code=1)
    result = state["result"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['id']}.json"
    path.write_text(_json_dumps(result), encoding="utf-8")
    typer.echo("")
    for line in summary_lines(result):
        typer.echo(line)
    typer.echo(f"saved {path}")


def _json_dumps(data) -> str:
    import json as _json

    return _json.dumps(data, indent=2) + "\n"


@prompts_app.command("remote-result")
def prompts_remote_result_command(run_id: str, prompt_id: str = "corp_capture") -> None:
    """Fetch a finished prod run and save it locally."""
    from app.prompts.evals import EVALS_DIR, summary_lines

    with _runner() as client:
        state = _runner_get(client, f"/evals/{run_id}")
    if state["status"] == "running":
        typer.echo(f"still running: {state['done']}/{state['total']}")
        return
    _save_remote(state, EVALS_DIR / prompt_id / "results", summary_lines)


@prompts_app.command("remote-runs")
def prompts_remote_runs_command() -> None:
    """Recent prod runs."""
    with _runner() as client:
        runs = _runner_get(client, "/evals")
    for run in runs[:20]:
        rate = run.get("pass_rate") or (run.get("summary") or {}).get("pass_rate")
        score = f"{rate:.0%}" if isinstance(rate, (int, float)) else run["status"]
        typer.echo(f"{run['id']}  {score}")


survey123_app = typer.Typer()
app.add_typer(survey123_app, name="survey123")


@survey123_app.command("check")
def survey123_check_command() -> None:
    """Query Survey123 once, as this environment, without printing any responses."""
    typer.echo(f"Referer: {settings.app_url}")
    try:
        result = query_responses(where="1=1", limit=1, offset=0, layer=0)
    except (Survey123NotConfigured, Survey123Unavailable) as exc:
        typer.echo(f"FAILED: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"OK: query returned {len(result['features'])} row(s) with limit=1")


@survey123_app.command("pull")
def survey123_pull_command(layer: int = 0) -> None:
    """Store the survey's validated responses, as an upload of its export would."""
    session = SessionLocal()
    try:
        result = pull_survey123(session, settings.dedup_salt, layer=layer)
    except (Survey123NotConfigured, Survey123Unavailable) as exc:
        typer.echo(f"FAILED: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except IngestFormatError as exc:
        typer.echo(f"FAILED: {exc.detail}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"duplicates_flagged={result.duplicates_flagged}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")


if __name__ == "__main__":
    app()
