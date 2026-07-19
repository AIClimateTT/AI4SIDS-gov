from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_sitrep_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_ingest_sitreps_command_reports_summary():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(
            app, ["ingest", "sitreps", "diego_martin_regional_corporati", str(FIXTURE_PATH)]
        )

        assert result.exit_code == 0, result.stdout
        assert "rows_read=3" in result.stdout
        assert "rows_inserted=3" in result.stdout
        assert "pii_columns_dropped=" in result.stdout
    finally:
        _reset_state()


def test_ingest_sitreps_command_flags_unmapped_corporation():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["ingest", "sitreps", "Not A Real Corp", str(FIXTURE_PATH)])

        assert result.exit_code == 0, result.stdout
        assert "Not A Real Corp" in result.stdout
    finally:
        _reset_state()
