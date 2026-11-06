import sqlite3

import pytest
import yaml

from app.core.template_catalog import (
    DEFINITIONS_DIR,
    get_template,
    list_templates,
    load_catalog,
)
from tests.test_migrations import run_alembic


def test_get_template_returns_the_yaml_with_its_version():
    template = get_template("minister_situation_report")

    raw = yaml.safe_load((DEFINITIONS_DIR / "minister_situation_report.yaml").read_text())
    assert template.version == raw["version"]
    assert template.title == raw["title"]


def test_unknown_template_returns_none():
    assert get_template("no_such_template") is None


def test_list_templates_has_every_shipped_file():
    names = {template.name for template in list_templates()}

    assert names == {path.stem for path in DEFINITIONS_DIR.glob("*.yaml")}


def _write(directory, name, metric):
    (directory / f"{name}.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "version": 100,
                "title": "T",
                "description": "D",
                "params": [],
                "data_requirements": [{"module": "survey123", "metric": metric}],
                "narration": {
                    "identity": "i",
                    "skills": {"compose": "c"},
                    "output_sections": ["a"],
                },
                "render": {},
            }
        )
    )


def test_invalid_metric_fails_catalog_load_naming_the_file(tmp_path):
    _write(tmp_path, "broken", "no_such_metric")

    with pytest.raises(ValueError, match=r"broken\.yaml.*no_such_metric"):
        load_catalog(tmp_path)


def test_a_valid_directory_loads(tmp_path):
    _write(tmp_path, "fine", "incident_count")

    assert set(load_catalog(tmp_path)) == {"fine"}


def test_drop_report_templates_migration_round_trips(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"

    def has_table() -> bool:
        conn = sqlite3.connect(db)
        try:
            return bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='report_templates'"
                ).fetchone()
            )
        finally:
            conn.close()

    run_alembic("upgrade", "head", database_url=url)
    assert has_table() is False
    run_alembic("downgrade", "d4c8a2f61b35", database_url=url)
    assert has_table() is True
    run_alembic("upgrade", "head", database_url=url)
    assert has_table() is False
