from datetime import datetime, timedelta, timezone

from app.modules.whatsapp.briefing import briefing_is_stale


def test_briefing_is_not_stale_without_a_report():
    assert (
        briefing_is_stale(
            briefing_report_id=None,
            draft_updated_at=datetime(2026, 8, 15, 16, 0),
            report_created_at=datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc),
        )
        is False
    )


def test_briefing_is_stale_when_working_set_is_newer():
    report_at = datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc)
    later = datetime(2026, 8, 15, 16, 1)
    assert (
        briefing_is_stale(
            briefing_report_id="r1",
            draft_updated_at=later,
            report_created_at=report_at,
        )
        is True
    )


def test_briefing_is_current_when_report_is_newer():
    report_at = datetime(2026, 8, 15, 16, 5, tzinfo=timezone.utc)
    earlier = datetime(2026, 8, 15, 16, 0)
    assert (
        briefing_is_stale(
            briefing_report_id="r1",
            draft_updated_at=earlier,
            report_created_at=report_at,
        )
        is False
    )


def test_equal_clocks_are_not_stale():
    moment = datetime(2026, 8, 15, 16, 0)
    aware = moment.replace(tzinfo=timezone.utc)
    assert (
        briefing_is_stale(
            briefing_report_id="r1",
            draft_updated_at=moment,
            report_created_at=aware,
        )
        is False
    )
    assert (
        briefing_is_stale(
            briefing_report_id="r1",
            draft_updated_at=moment + timedelta(microseconds=1),
            report_created_at=aware,
        )
        is True
    )
