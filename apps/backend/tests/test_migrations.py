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
        "events",
        "submissions",
        "sitrep_incidents",
        "situation_logs",
        "capture_sessions",
        "users",
        "refresh_tokens",
        "login_otps",
        "workflow_events",
        "report_ratings",
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

    assert "error" in reports
    assert reports["error"][3] == 0
    assert "quality_eval" in reports
    assert reports["quality_eval"][3] == 0



def test_capture_sessions_have_sitrep_columns(tmp_path):
    import sqlite3

    db = tmp_path / "fresh.db"
    result = run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")
    assert result.returncode == 0, result.stderr
    conn = sqlite3.connect(db)

    columns = {r[1]: r for r in conn.execute("PRAGMA table_info(capture_sessions)")}
    for name in (
        "report_id",
        "sitrep_markdown",
        "sitrep_fact_table",
        "sitrep_violations",
        "sitrep_status",
        "sitrep_generated_at",
        "sitrep_source_updated_at",
    ):
        assert name in columns, f"{name} missing from capture_sessions"
        assert columns[name][3] == 0, f"{name} should be nullable"

    report_fks = [
        fk
        for fk in conn.execute("PRAGMA foreign_key_list(capture_sessions)")
        if fk[3] == "report_id"
    ]
    assert report_fks, "report_id should FK to reports"
    assert report_fks[0][2] == "reports"
    assert report_fks[0][4] == "id"
    on_delete = (report_fks[0][6] or "NO ACTION").upper()
    assert on_delete != "CASCADE", "issued reports must survive session deletion"


def test_downgrade_base_succeeds_from_head(tmp_path):
    db = tmp_path / "fresh.db"
    run_alembic("upgrade", "head", database_url=f"sqlite:///{db}")

    result = run_alembic("downgrade", "base", database_url=f"sqlite:///{db}")

    assert result.returncode == 0, result.stderr
