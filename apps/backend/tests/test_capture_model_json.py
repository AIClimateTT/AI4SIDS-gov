import sqlite3

import pytest

from app.modules.capture.model_json import parse_model_json
from tests.test_migrations import run_alembic


def test_parse_model_json_strips_fences():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_model_json_rejects_non_object():
    with pytest.raises(ValueError):
        parse_model_json("[1]")


def test_drop_whatsapp_migration_round_trips(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"

    def has_table() -> bool:
        conn = sqlite3.connect(db)
        try:
            return bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='whatsapp_drafts'"
                ).fetchone()
            )
        finally:
            conn.close()

    run_alembic("upgrade", "head", database_url=url)
    assert has_table() is False
    run_alembic("downgrade", "c6e2f4a81d07", database_url=url)
    assert has_table() is True
    run_alembic("upgrade", "head", database_url=url)
    assert has_table() is False
