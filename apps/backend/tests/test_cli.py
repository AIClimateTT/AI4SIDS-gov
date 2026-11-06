from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
VALIDATED_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small_validated.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def test_ingest_survey123_command_reports_summary():
    reset_registry()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["ingest", "survey123", str(VALIDATED_FIXTURE_PATH)])

        assert result.exit_code == 0, result.stdout
        assert "rows_read=21" in result.stdout
        assert "rows_inserted=21" in result.stdout
        assert "duplicates_flagged=2" in result.stdout
    finally:
        reset_registry()
        if DEV_DB_PATH.exists():
            DEV_DB_PATH.unlink()


def test_ingest_unknown_module_errors():
    reset_registry()

    result = runner.invoke(app, ["ingest", "not_a_real_module", str(FIXTURE_PATH)])

    assert result.exit_code == 2
    reset_registry()
