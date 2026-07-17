from pathlib import Path

from typer.testing import CliRunner

from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_import_template_command_reports_version_one():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(
            app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")]
        )

        assert result.exit_code == 0, result.stdout
        assert "single_region_report" in result.stdout
        assert "version 1" in result.stdout
    finally:
        _reset_state()


def test_import_template_command_twice_increments_version():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")])
        result = runner.invoke(
            app, ["templates", "import", str(TEMPLATES_DIR / "single_region_report.yaml")]
        )

        assert result.exit_code == 0, result.stdout
        assert "version 2" in result.stdout
    finally:
        _reset_state()


def test_import_all_command_imports_both_default_templates():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        result = runner.invoke(app, ["templates", "import-all", str(TEMPLATES_DIR)])

        assert result.exit_code == 0, result.stdout
        assert "minister_regional_comparison" in result.stdout
        assert "single_region_report" in result.stdout
    finally:
        _reset_state()
