from pathlib import Path
from typing import Optional

import typer
from sqlalchemy.orm import Session

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import get_module, register_module
from app.core.template_store import (
    create_template_version,
    get_latest_template_version,
    import_template_directory,
    list_latest_templates,
)
from app.db import SessionLocal
from app.modules.survey123.module import get_survey123_module, survey123_module
from app.templates.loader import load_template

app = typer.Typer()
ingest_app = typer.Typer()
templates_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")
app.add_typer(templates_app, name="templates")


def _ensure_survey123_registered() -> None:
    if get_module("survey123") is None:
        register_module(get_survey123_module())


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

    if incidents is not None and event_id is None:
        typer.echo(
            "a submission carrying incidents must name an event; pass --event-id",
            err=True,
        )
        raise typer.Exit(code=1)

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
    _ensure_survey123_registered()
    session = SessionLocal()
    try:
        template = get_latest_template_version(template_name, session)
        if template is None:
            typer.echo(f"unknown template: {template_name}", err=True)
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


if __name__ == "__main__":
    app()
