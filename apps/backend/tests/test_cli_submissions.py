import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

import app.modules.sitreps.models  # noqa: F401 -- registers sitreps tables on Base.metadata
from app.core.registry import reset_registry
from app.db import Base, SessionLocal, engine as db_engine
from app.modules.sitreps.store import create_event
from cli import app

runner = CliRunner()

INCIDENTS_PATH = Path(__file__).parent.parent / "fixtures" / "sample_submission_incidents.csv"
LOGS_PATH = Path(__file__).parent.parent / "fixtures" / "sample_submission_logs.csv"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"
CORP = "diego_martin_regional_corporati"


def _reset_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def test_submissions_command_ingests_incidents_and_logs():
    _reset_state()

    Base.metadata.create_all(db_engine)

    session = SessionLocal()
    try:
        event = create_event(
            session,
            corporation=CORP,
            title="Adverse Weather June 2023",
            hazard_type="wind",
            started_at=datetime(2023, 6, 27),
        )
        event_id = event.id
    finally:
        session.close()

    try:
        result = runner.invoke(
            app,
            [
                "submissions",
                CORP,
                "2023-06-30T16:00:00",
                "--incidents",
                str(INCIDENTS_PATH),
                "--logs",
                str(LOGS_PATH),
                "--event-id",
                str(event_id),
            ],
        )

        assert result.exit_code == 0, result.stdout
        body = json.loads(result.stdout)
        assert body["incidents_inserted"] == 3
        assert body["logs_inserted"] == 5
    finally:
        _reset_state()
