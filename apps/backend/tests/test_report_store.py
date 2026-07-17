from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.core.citation_check import CitationViolation
from app.core.contracts import Citation, Fact, FactTable
from app.core.engine import GeneratedReport
from app.core.report_store import get_report, save_report
from app.db import Base, make_engine


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_generated_report(status="ok", violations=None, template_version=1) -> GeneratedReport:
    citation = Citation(
        cid="C001",
        module="survey123",
        description="test",
        query_ref="incident_count()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
    )
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=citation,
    )
    fact_table = FactTable(
        request_id="req-1",
        template="minister_regional_comparison",
        template_version=template_version,
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=[fact],
        gaps=[],
    )
    return GeneratedReport(
        request_id="req-1",
        template="minister_regional_comparison",
        template_version=template_version,
        params={"date_from": "2024-06-01", "date_to": "2024-06-30"},
        fact_table=fact_table,
        narrative="There were 19 incidents recorded [C001].",
        status=status,
        violations=violations or [],
        markdown="# Test Report\n\nThere were 19 incidents recorded [C001].",
    )


def test_save_report_persists_all_fields(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()

    saved = save_report(report, session)

    assert saved.id == "req-1"
    assert saved.template == "minister_regional_comparison"
    assert saved.params == {"date_from": "2024-06-01", "date_to": "2024-06-30"}
    assert saved.status == "ok"
    assert saved.narrative == "There were 19 incidents recorded [C001]."
    assert saved.markdown.startswith("# Test Report")
    assert saved.fact_table["request_id"] == "req-1"
    assert saved.violations == []


def test_save_report_persists_violations(tmp_path):
    session = make_session(tmp_path)
    violation = CitationViolation(
        kind="invented_number", detail="test detail", sentence="Bad sentence.", token="999"
    )
    report = make_generated_report(status="needs_review", violations=[violation])

    saved = save_report(report, session)

    assert saved.status == "needs_review"
    assert len(saved.violations) == 1
    assert saved.violations[0]["kind"] == "invented_number"
    assert saved.violations[0]["token"] == "999"


def test_get_report_retrieves_saved_report(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()
    save_report(report, session)

    fetched = get_report("req-1", session)

    assert fetched is not None
    assert fetched.id == "req-1"


def test_get_report_returns_none_for_unknown_id(tmp_path):
    session = make_session(tmp_path)

    assert get_report("does-not-exist", session) is None


def test_save_report_persists_default_template_version(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report()

    saved = save_report(report, session)

    assert saved.template_version == 1


def test_save_report_persists_explicit_template_version(tmp_path):
    session = make_session(tmp_path)
    report = make_generated_report(template_version=3)

    saved = save_report(report, session)

    assert saved.template_version == 3
