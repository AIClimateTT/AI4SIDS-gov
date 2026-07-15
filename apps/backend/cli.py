from pathlib import Path

import typer

from app.core.engine import generate_report
from app.core.llm import get_default_llm_client
from app.core.registry import (
    get_module,
    get_template,
    list_templates,
    register_module,
    register_template,
)
from app.db import SessionLocal
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_templates_from_directory

TEMPLATES_DIR = Path(__file__).parent / "app" / "templates" / "definitions"

app = typer.Typer()
ingest_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")


def _ensure_templates_loaded() -> None:
    if not list_templates():
        for template in load_templates_from_directory(TEMPLATES_DIR):
            register_template(template)


@ingest_app.command("survey123")
def ingest_survey123(file_path: Path) -> None:
    if get_module("survey123") is None:
        register_module(survey123_module)

    result = get_module("survey123").ingest(file_path)

    typer.echo(f"rows_read={result.rows_read}")
    typer.echo(f"rows_inserted={result.rows_inserted}")
    typer.echo(f"rows_updated={result.rows_updated}")
    typer.echo(f"duplicates_flagged={result.duplicates_flagged}")
    typer.echo(f"unmapped_values={result.unmapped_values}")
    typer.echo(f"pii_columns_dropped={result.pii_columns_dropped}")


@app.command("list-templates")
def list_templates_command() -> None:
    _ensure_templates_loaded()
    for template in list_templates():
        typer.echo(f"{template.name}: {template.title}")


@app.command()
def generate(
    template_name: str,
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
    corporation: str = typer.Option(None, "--corporation"),
    community: str = typer.Option(None, "--community"),
) -> None:
    _ensure_templates_loaded()
    if get_module("survey123") is None:
        register_module(survey123_module)

    template = get_template(template_name)
    if template is None:
        typer.echo(f"unknown template: {template_name}", err=True)
        raise typer.Exit(code=1)

    params = {
        "date_from": date_from,
        "date_to": date_to,
        "corporation": corporation,
        "community": community,
    }

    session = SessionLocal()
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
