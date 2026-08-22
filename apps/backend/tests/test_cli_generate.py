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


def test_list_templates_shows_every_shipped_template():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        result = runner.invoke(app, ["list-templates"])

        assert result.exit_code == 0, result.stdout
        assert "minister_situation_report" in result.stdout
        assert "field_data_region_review" in result.stdout
    finally:
        _reset_state()


def test_generate_minister_situation_report_produces_markdown_report(monkeypatch):
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
                "minister_situation_report",
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

        result = runner.invoke(app, ["generate", "minister_situation_report", "--date-from", "2024-06-01"])

        assert result.exit_code == 1
    finally:
        _reset_state()


SITREP_TEMPLATE_YAML = """
name: corp_sitrep_only
title: Corp SITREP Only
description: A template whose data comes from the sitreps module.
params: []
data_requirements:
  - module: sitreps
    metric: incident_count
narration:
  identity: test
  skills:
    compose: Summarise the corporation's own situation reports.
  output_sections: [situation_overview]
render:
  format: markdown
  include_citation_appendix: true
"""


def test_generate_can_run_a_sitreps_template(monkeypatch, tmp_path):
    # cli generate registered survey123 and nothing else, so a template naming
    # a sitreps metric died with "unknown data module: sitreps" while the same
    # template generated fine through the API.
    #
    # reset_registry() before the generate invocation on purpose: each CLI
    # invocation is a fresh process in reality, and the import above happens to
    # register every module as a side effect of template validation. Without
    # the reset this test would exercise leaked state, not the command.
    from app.core.registry import reset_registry as clear_modules

    monkeypatch.setattr(llm_module.settings, "llm_provider", "fake")

    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        template_path = tmp_path / "corp_sitrep_only.yaml"
        template_path.write_text(SITREP_TEMPLATE_YAML)
        imported = runner.invoke(app, ["templates", "import", str(template_path)])
        assert imported.exit_code == 0, imported.output

        clear_modules()

        result = runner.invoke(app, ["generate", "corp_sitrep_only"])

        assert "unknown data module" not in result.output
        assert result.exit_code == 0, result.output
    finally:
        _reset_state()


def test_generate_rejects_a_corporation_that_is_not_one_of_the_fourteen():
    # A typo matches no row, so every metric returns a confident zero and the
    # report reads as an authoritative "nothing happened" for that region.
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])

        result = runner.invoke(
            app,
            [
                "generate",
                "field_data_region_review",
                "--corporation",
                "Diego Martin",
                "--date-from",
                "2024-06-01",
                "--date-to",
                "2024-06-30",
            ],
        )

        assert result.exit_code == 1
        assert "unknown corporation" in result.output.lower()
    finally:
        _reset_state()


def test_generate_accepts_a_canonical_corporation(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_provider", "fake")

    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(app, ["templates", "import-all", str(Path(__file__).parent.parent / "app" / "templates" / "definitions")])
        runner.invoke(app, ["ingest", "survey123", str(FIXTURE_PATH)])

        result = runner.invoke(
            app,
            [
                "generate",
                "field_data_region_review",
                "--corporation",
                "diego_martin_regional_corporati",
                "--date-from",
                "2024-06-01",
                "--date-to",
                "2024-06-30",
            ],
        )

        assert result.exit_code == 0, result.stdout
    finally:
        _reset_state()


def test_generate_rejects_corp_situation_report():
    _reset_state()
    Base.metadata.create_all(db_engine)

    try:
        runner.invoke(
            app,
            [
                "templates",
                "import-all",
                str(Path(__file__).parent.parent / "app" / "templates" / "definitions"),
            ],
        )
        result = runner.invoke(
            app,
            [
                "generate",
                "corp_situation_report",
                "--corporation",
                "diego_martin_regional_corporati",
            ],
        )
        assert result.exit_code == 1
        assert "issued from capture" in result.output.lower()
    finally:
        _reset_state()


def test_generate_unknown_template_errors():
    _reset_state()

    result = runner.invoke(app, ["generate", "not_a_real_template"])

    assert result.exit_code == 1
    _reset_state()
