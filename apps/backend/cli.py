from pathlib import Path
from typing import Optional

import typer
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import ensure_default_modules_registered
from app.core.template_store import (
    create_template_version,
    get_latest_template_version,
    import_template_directory,
    list_latest_templates,
)
from app.db import SessionLocal
from app.modules.survey123.module import survey123_module
from app.modules.survey123.normalize import CANONICAL_CORPORATIONS
from app.templates.loader import load_template

app = typer.Typer()
ingest_app = typer.Typer()
templates_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")
app.add_typer(templates_app, name="templates")


@ingest_app.command("survey123")
def ingest_survey123(file_path: Path) -> None:
    result = survey123_module.ingest(file_path)

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


@templates_app.command("import")
def import_template(yaml_path: Path) -> None:
    template = load_template(yaml_path)
    session: Session = SessionLocal()
    try:
        stored = create_template_version(template, session)
    finally:
        session.close()
    typer.echo(f"imported {stored.name} as version {stored.version}")


@templates_app.command("import-all")
def import_all_templates(directory: Path) -> None:
    session: Session = SessionLocal()
    try:
        stored = import_template_directory(directory, session)
    finally:
        session.close()
    for template in stored:
        typer.echo(f"imported {template.name} as version {template.version}")


@app.command("list-templates")
def list_templates_command() -> None:
    session = SessionLocal()
    try:
        templates = list_latest_templates(session)
    finally:
        session.close()
    for template in templates:
        typer.echo(f"{template.name} (v{template.version}): {template.title}")


@app.command()
def generate(
    template_name: str,
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
    corporation: str = typer.Option(None, "--corporation"),
    community: str = typer.Option(None, "--community"),
) -> None:
    # Every registered module, not just survey123: a template naming a sitreps
    # metric raised "unknown data module: sitreps" from the CLI while the same
    # template generated fine through the API.
    ensure_default_modules_registered()

    # A corporation that is not one of the fourteen matches no row, and every
    # metric reports a confident zero for it. Rejected before any query runs,
    # exactly as POST /reports does.
    if corporation is not None and corporation not in CANONICAL_CORPORATIONS:
        typer.echo(f"unknown corporation: {corporation}", err=True)
        raise typer.Exit(code=1)

    session = SessionLocal()
    try:
        template = get_latest_template_version(template_name, session)
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
    from app.core.template_store import get_template_version
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
            template = get_template_version(row.template, row.template_version, session)
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


if __name__ == "__main__":
    app()
