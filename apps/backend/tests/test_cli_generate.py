from pathlib import Path

from typer.testing import CliRunner

import app.core.llm as llm_module
from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from cli import app

runner = CliRunner()

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_small.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_list_templates_shows_both_real_templates():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        result = runner.invoke(app, ["list-templates"])

        assert result.exit_code == 0, result.stdout
        assert "minister_regional_comparison" in result.stdout
        assert "single_region_report" in result.stdout
    finally:
        _reset_state()


def test_generate_minister_regional_comparison_produces_markdown_report(monkeypatch):
    # Force the fake, network-free provider regardless of Settings.llm_provider's
    # real-world default ("ollama") — this test must stay testable without a
    # network connection or a running Ollama server, per PLAN.md's "everything
    # except core/llm.py must be testable without a network" guardrail. Real
    # Ollama coverage is exercised manually (see the Ollama plan's Task 1 Step 9),
    # never in the automated suite.
    monkeypatch.setattr(llm_module.settings, "llm_provider", "fake")

    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

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
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        result = runner.invoke(app, ["generate", "minister_regional_comparison", "--date-from", "2024-06-01"])

        assert result.exit_code == 1
    finally:
        _reset_state()


def test_generate_unknown_template_errors():
    _reset_state()

    result = runner.invoke(app, ["generate", "not_a_real_template"])

    assert result.exit_code == 1
    _reset_state()
