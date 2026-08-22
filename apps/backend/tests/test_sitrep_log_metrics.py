from datetime import datetime
from types import SimpleNamespace

from app.modules.sitreps.log_metrics import activity_log, relief_stock_summary
from app.modules.sitreps.models import Event, SituationLog, Submission


def test_relief_stock_summary_reads_quantified_logs_only():
    rows = [
        SimpleNamespace(
            statement="Tarpaulin distribution",
            item="tarpaulins",
            quantity=10,
            unit="units",
            status="completed",
            category="relief_distributed",
            record_ref="c:log:1",
            global_id=None,
        ),
        SimpleNamespace(
            statement="Officers dispatched",
            item=None,
            quantity=None,
            unit=None,
            status="completed",
            category="activity",
            record_ref="c:log:2",
            global_id=None,
        ),
    ]

    facts = relief_stock_summary({"corporation": "arima_borough_corporation"}, rows=rows)

    assert len(facts) == 1
    assert facts[0].value == 10
    assert facts[0].scope["item"] == "tarpaulins"


def test_activity_log_reads_statements_without_quantity():
    rows = [
        SimpleNamespace(
            statement="Officers dispatched to aid injured individual",
            item=None,
            quantity=None,
            unit=None,
            status="completed",
            category="activity",
            record_ref="c:log:2",
            global_id=None,
        ),
        SimpleNamespace(
            statement="Sandbag stock remaining",
            item="sandbags",
            quantity=100,
            unit="bags",
            status="in_stock",
            category="resource",
            record_ref="c:log:3",
            global_id=None,
        ),
    ]

    facts = activity_log({"corporation": "arima_borough_corporation"}, rows=rows)

    assert len(facts) == 1
    assert facts[0].value == "Officers dispatched to aid injured individual"


def test_relief_stock_summary_scopes_to_submission_id(tmp_path):
    from sqlalchemy.orm import sessionmaker

    from app.db import Base, make_engine

    engine = make_engine(f"sqlite:///{tmp_path}/logs.db")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    event = Event(
        corporation="arima_borough_corporation",
        title="Flood",
        hazard_type="flood",
        started_at=datetime(2026, 8, 21),
        created_at=datetime(2026, 8, 21),
    )
    db.add(event)
    db.flush()
    first = Submission(
        corporation="arima_borough_corporation",
        event_id=event.id,
        as_at=datetime(2026, 8, 21, 10),
        sequence_no=1,
        ingested_at=datetime(2026, 8, 21, 10),
    )
    second = Submission(
        corporation="arima_borough_corporation",
        event_id=event.id,
        as_at=datetime(2026, 8, 21, 16),
        sequence_no=2,
        ingested_at=datetime(2026, 8, 21, 16),
    )
    db.add_all([first, second])
    db.flush()
    db.add(
        SituationLog(
            submission_id=first.id,
            category="relief_distributed",
            statement="Old tarps",
            item="tarpaulins",
            quantity=1,
            unit="units",
            status="completed",
        )
    )
    db.add(
        SituationLog(
            submission_id=second.id,
            category="relief_distributed",
            statement="New tarps",
            item="tarpaulins",
            quantity=10,
            unit="units",
            status="completed",
        )
    )
    db.commit()

    facts = relief_stock_summary({"submission_id": second.id}, db)
    db.close()
    assert len(facts) == 1
    assert facts[0].value == 10
