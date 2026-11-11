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
    tables = Base.metadata.sorted_tables
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
