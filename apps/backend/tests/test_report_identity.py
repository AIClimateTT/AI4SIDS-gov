import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.llm import FakeLLMClient
from app.core.report_identity import (
    clean_markdown,
    report_kind,
    report_period,
    report_title,
)
from app.core.report_models import Report
from app.core.report_store import save_report
from app.core.engine import generate_report
from app.core.template_catalog import get_template
from app.db import Base, SessionLocal, engine as db_engine
from tests.test_migrations import run_alembic

ARIMA = "arima_borough_corporation"


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


def _row(template="survey123_summary", version=100, status="ok", params=None, **extra) -> str:
    db = SessionLocal()
    row = Report(
        id=str(uuid.uuid4()),
        template=template,
        template_version=version,
        params=params if params is not None else {},
        fact_table=extra.pop("fact_table", {}),
        narrative="",
        markdown=extra.pop("markdown", ""),
        status=status,
        violations=[],
        created_at=extra.pop("created_at", datetime(2026, 11, 1, tzinfo=timezone.utc)),
        **extra,
    )
    db.add(row)
    db.commit()
    report_id = row.id
    db.close()
    return report_id


@pytest.mark.parametrize(
    "template,kind",
    [
        ("corp_situation_report", "corporation"),
        ("minister_situation_report", "minister"),
        ("survey123_summary", "survey123"),
        ("field_data_region_review", "survey123"),
        ("whatsapp_hour_briefing", "other"),
    ],
)
def test_kind_for_each_template(template, kind):
    assert report_kind(template) == kind


def test_title_for_a_corporation_report_with_a_number():
    assert (
        report_title("corp_situation_report", {"corporation": ARIMA}, 2)
        == "Arima Borough Corporation report #2"
    )


def test_title_without_a_corporation_still_reads():
    assert report_title("corp_situation_report", {}, None) == "Corporation report"


def test_titles_for_the_other_kinds():
    assert report_title("minister_situation_report", {}, None) == "Minister report"
    assert report_title("survey123_summary", {}, None) == "Survey123 summary"
    assert (
        report_title("survey123_summary", {"corporation": ARIMA}, None)
        == "Survey123 summary: Arima Borough Corporation"
    )
    assert report_title("whatsapp_hour_briefing", {}, None) == "WhatsApp briefing"


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"date_from": "2026-01-01", "date_to": "2026-11-02"}, "1 Jan – 2 Nov 2026"),
        ({"date_from": "2025-12-01", "date_to": "2026-01-02"}, "1 Dec 2025 – 2 Jan 2026"),
        ({"date_from": "2026-06-30", "date_to": "2026-06-30"}, "30 Jun 2026"),
        ({"date_from": "2026-01-01"}, "From 1 Jan 2026"),
        ({"date_to": "2026-11-02"}, "To 2 Nov 2026"),
        ({"date_from": "", "date_to": ""}, None),
        ({"date_from": "not-a-date"}, None),
        ({}, None),
    ],
)
def test_period_formats(params, expected):
    assert report_period(params) == expected


def test_clean_markdown_falls_back_to_stripping_old_reports():
    old = Report(markdown="There were 3 incidents [C001].", final_markdown=None)
    new = Report(markdown="There were 3 incidents [C001].", final_markdown="Clean text")

    assert clean_markdown(old) == "There were 3 incidents."
    assert clean_markdown(new) == "Clean text"


def test_generated_report_stores_final_markdown():
    db = SessionLocal()
    generated = generate_report(
        get_template("minister_situation_report"),
        {"date_from": "2026-01-01", "date_to": "2026-01-02"},
        db,
        FakeLLMClient(),
    )
    row = save_report(generated, db)

    assert row.final_markdown == generated.final_markdown
    assert row.final_markdown.rstrip().endswith("END OF REPORT")
    db.close()


def test_list_items_carry_the_identity():
    _row(
        "corp_situation_report",
        params={"corporation": ARIMA},
        fact_table={"params": {"report_number": 3}},
    )

    item = TestClient(create_app()).get("/reports").json()["items"][0]

    assert item["kind"] == "corporation"
    assert item["title"] == "Arima Borough Corporation report #3"
    assert item["verified"] is False
    assert item["older_format"] is False


def test_only_survey123_is_verified():
    report_id = _row("survey123_summary", params={"date_from": "2026-01-01"})

    body = TestClient(create_app()).get(f"/reports/{report_id}").json()

    assert body["verified"] is True
    assert body["period"] == "From 1 Jan 2026"


def test_detail_gives_clean_text_for_an_old_report():
    report_id = _row(markdown="3 incidents [C001].")

    body = TestClient(create_app()).get(f"/reports/{report_id}").json()

    assert body["final_markdown"] == "3 incidents."


def test_reports_filter_by_kind():
    _row("minister_situation_report")
    _row("survey123_summary")
    _row("corp_situation_report", params={"corporation": ARIMA})

    body = TestClient(create_app()).get("/reports", params={"kind": "minister"}).json()

    assert [item["kind"] for item in body["items"]] == ["minister"]


def test_older_reports_are_hidden_unless_asked():
    _row("minister_situation_report", version=1, status="needs_review")
    _row("minister_situation_report", version=100)
    client = TestClient(create_app())

    assert client.get("/reports").json()["total"] == 1
    everything = client.get("/reports", params={"include_older": True}).json()
    assert everything["total"] == 2
    assert {item["older_format"] for item in everything["items"]} == {True, False}


def test_reports_search_reaches_the_corporation():
    _row("corp_situation_report", params={"corporation": ARIMA})
    _row("minister_situation_report")

    body = TestClient(create_app()).get("/reports", params={"q": "arima"}).json()

    assert body["total"] == 1


def test_overview_ignores_older_reports():
    _row("minister_situation_report", version=1, status="needs_review")
    _row("minister_situation_report", version=100, status="needs_review")

    body = TestClient(create_app()).get("/overview").json()

    assert body["needs_review_count"] == 1
    assert len(body["recent_reports"]) == 1
    assert body["recent_reports"][0]["title"] == "Minister report"


def test_report_final_markdown_migration_round_trips(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"

    def columns() -> set[str]:
        conn = sqlite3.connect(db)
        try:
            return {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
        finally:
            conn.close()

    assert run_alembic("upgrade", "head", database_url=url).returncode == 0
    assert "final_markdown" in columns()
    assert run_alembic("downgrade", "e7d2b5c04a91", database_url=url).returncode == 0
    assert "final_markdown" not in columns()


def test_created_at_says_it_is_utc_so_browsers_convert_it():
    report_id = _row(created_at=datetime(2026, 11, 6, 4, 23))
    client = TestClient(create_app())

    for value in (
        client.get(f"/reports/{report_id}").json()["created_at"],
        client.get("/reports").json()["items"][0]["created_at"],
        client.get("/overview").json()["recent_reports"][0]["created_at"],
    ):
        assert value.endswith(("Z", "+00:00"))
