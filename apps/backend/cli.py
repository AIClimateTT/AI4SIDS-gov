from pathlib import Path

import typer

from app.core.registry import get_module, register_module
from app.modules.survey123.module import survey123_module

app = typer.Typer()
ingest_app = typer.Typer()
app.add_typer(ingest_app, name="ingest")


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


if __name__ == "__main__":
    app()
