"""Migrations must run from an empty database.

Run in a subprocess with DATABASE_URL set, because alembic/env.py overrides
sqlalchemy.url from app.config.settings, which is cached at import time — an
in-process alembic call would ignore whatever path the test chose and migrate
the shared dev database instead.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent


def run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env={
            "PATH": "/usr/bin:/bin",
            "DATABASE_URL": database_url,
            "HOME": str(Path.home()),
        },
        capture_output=True,
        text=True,
    )


def test_upgrade_head_succeeds_from_an_empty_database(tmp_path):
    # Provisioning a fresh environment is exactly this command. It failed on
    # SQLite because three migrations called op.alter_column to drop a
    # server_default, and SQLite has no ALTER COLUMN at all.
    db = tmp_path / "fresh.db"

    result = run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")

    assert result.returncode == 0, result.stderr
    assert db.exists()


def test_every_table_exists_after_upgrade_head(tmp_path):
    import sqlite3

    db = tmp_path / "fresh.db"
    run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")

    names = {
        row[0]
        for row in sqlite3.connect(db).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    assert {
        "field_observations",
        "reports",
        "report_templates",
        "events",
        "submissions",
        "sitrep_incidents",
        "situation_logs",
    } <= names


def test_the_backfilled_columns_keep_their_shape(tmp_path):
    # The three migrations add a NOT NULL column with a server_default so
    # existing rows backfill, then drop the default so the schema matches the
    # model. Both halves must survive the fix.
    import sqlite3

    db = tmp_path / "fresh.db"
    run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")
    conn = sqlite3.connect(db)

    reports = {r[1]: r for r in conn.execute("PRAGMA table_info(reports)")}

    for column in ("template_version", "data_requirements"):
        assert column in reports, f"{column} missing from reports"
        assert reports[column][3] == 1, f"{column} should be NOT NULL"
        assert reports[column][4] is None, f"{column} should have no server default"


def test_downgrade_base_succeeds_from_head(tmp_path):
    db = tmp_path / "fresh.db"
    run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")

    result = run_alembic("downgrade", "base", database_url=f"sqlite:///{db}")

    assert result.returncode == 0, result.stderr
