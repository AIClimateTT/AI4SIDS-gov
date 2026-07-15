from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry, reset_template_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    reset_template_registry()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_list_templates_shows_both_real_templates():
    _reset_state()

    result = runner.invoke(app, ["list-templates"])

    assert result.exit_code == 0, result.stdout
    assert "minister_regional_comparison" in result.stdout
    assert "single_region_report" in result.stdout
    _reset_state()


def test_generate_minister_regional_comparison_produces_markdown_report():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        ingest_result = runner.invoke(app, ["ingest", "survey123", str(FIXTURE_PATH)])
        assert ingest_result.exit_code == 0, ingest_result.stdout

        result = runner.invoke(
            app,
            [
                "generate",
                "minister_regional_comparison",
                "--date-from",
                "2024-06-01",
                "--date-to",
                "2024-06-30",
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "# " in result.stdout
        assert "## Citation Appendix" in result.stdout
    finally:
        _reset_state()


def test_generate_missing_required_param_errors():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["generate", "minister_regional_comparison", "--date-from", "2024-06-01"])

        assert result.exit_code == 1
    finally:
        _reset_state()


def test_generate_unknown_template_errors():
    _reset_state()

    result = runner.invoke(app, ["generate", "not_a_real_template"])

    assert result.exit_code == 1
    _reset_state()
