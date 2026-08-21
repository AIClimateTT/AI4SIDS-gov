from unittest.mock import MagicMock

from app.config import Settings
from app.core.jobs import resolve_job_backend
from app.jobs.queue import apply_schema


def test_sqlite_defaults_to_eager(monkeypatch):
    monkeypatch.setattr(
        "app.core.jobs.settings",
        Settings(_env_file=None, database_url="sqlite:///./dev.db", job_backend=None),
    )
    assert resolve_job_backend() == "eager"


def test_postgres_defaults_to_procrastinate(monkeypatch):
    monkeypatch.setattr(
        "app.core.jobs.settings",
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@localhost:5432/dmcu",
            job_backend=None,
        ),
    )
    assert resolve_job_backend() == "procrastinate"


def test_explicit_job_backend_wins(monkeypatch):
    monkeypatch.setattr(
        "app.core.jobs.settings",
        Settings(_env_file=None, database_url="sqlite:///./dev.db", job_backend="procrastinate"),
    )
    assert resolve_job_backend() == "procrastinate"


class _Open:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def test_apply_schema_skips_sqlite(monkeypatch):
    apply = MagicMock()
    monkeypatch.setattr(
        "app.jobs.queue.settings",
        Settings(_env_file=None, database_url="sqlite:///./dev.db"),
    )
    monkeypatch.setattr("procrastinate.schema.SchemaManager.apply_schema", apply)

    apply_schema()

    apply.assert_not_called()


def test_apply_schema_skips_when_jobs_table_exists(monkeypatch):
    connector = MagicMock()
    connector.execute_query_one.return_value = {"name": "procrastinate_jobs"}
    apply = MagicMock()
    monkeypatch.setattr(
        "app.jobs.queue.settings",
        Settings(_env_file=None, database_url="postgresql://u:p@localhost:5432/dmcu"),
    )
    monkeypatch.setattr("app.jobs.queue.app.open", lambda: _Open())
    monkeypatch.setattr(
        "app.jobs.queue.app.connector.get_sync_connector", lambda: connector
    )
    monkeypatch.setattr("procrastinate.schema.SchemaManager.apply_schema", apply)

    apply_schema()

    apply.assert_not_called()


def test_apply_schema_creates_when_missing(monkeypatch):
    connector = MagicMock()
    connector.execute_query_one.return_value = {"name": None}
    apply = MagicMock()
    monkeypatch.setattr(
        "app.jobs.queue.settings",
        Settings(_env_file=None, database_url="postgresql://u:p@localhost:5432/dmcu"),
    )
    monkeypatch.setattr("app.jobs.queue.app.open", lambda: _Open())
    monkeypatch.setattr(
        "app.jobs.queue.app.connector.get_sync_connector", lambda: connector
    )
    monkeypatch.setattr("procrastinate.schema.SchemaManager.apply_schema", apply)

    apply_schema()

    apply.assert_called_once()
