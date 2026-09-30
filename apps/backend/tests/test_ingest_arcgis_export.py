"""A Survey123 CSV exactly as ArcGIS exports it, with nothing fixed in Excel.

The export differs from the hand-built fixture in ways that each used to lose
data: a byte-order mark, US dates in UTC, question labels with trailing spaces
and repeats, and yes/no answers instead of True/False.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.localtime import local_date, to_local
from app.modules.survey123.ingest import (
    ingest_csv,
    normalize_headers,
    parse_calendar_date,
    parse_timestamp,
)
from app.modules.survey123.metrics import apply_common_filters
from app.modules.survey123.models import FieldObservation
from tests.test_ingest import make_session

EXPORT_PATH = Path(__file__).parent.parent / "fixtures" / "sample_arcgis_export.csv"


def ingest_export(tmp_path):
    session = make_session(tmp_path)
    result = ingest_csv(EXPORT_PATH, session, salt="test-salt")
    rows = {r.object_id: r for r in session.scalars(select(FieldObservation))}
    return session, result, rows


def test_export_ingests_every_row(tmp_path):
    _session, result, rows = ingest_export(tmp_path)

    assert result.rows_inserted == 3
    assert sorted(rows) == [1, 2, 3]


def test_export_timestamps_are_stored_as_utc(tmp_path):
    _session, _result, rows = ingest_export(tmp_path)

    created = rows[1].creation_date.replace(tzinfo=timezone.utc)
    assert created == datetime(2021, 4, 21, 15, 36, 49, tzinfo=timezone.utc)
    assert to_local(created).hour == 11


def test_evening_submission_counts_on_the_trinidad_day(tmp_path):
    _session, _result, rows = ingest_export(tmp_path)

    # 1:30 AM UTC on the 23rd is 9:30 PM on the 22nd in Trinidad.
    assert local_date(rows[2].creation_date) == date(2021, 4, 22)


def test_export_event_date_is_the_trinidad_calendar_day(tmp_path):
    _session, _result, rows = ingest_export(tmp_path)

    assert rows[1].event_date == date(2021, 4, 19)
    assert rows[1].assessment_date == date(2021, 4, 21)
    assert rows[3].event_date == date(2022, 12, 4)


def test_yes_answers_are_read_as_true(tmp_path):
    _session, _result, rows = ingest_export(tmp_path)

    assert rows[1].injuries_occurred is True
    assert rows[1].injuries_count == 2
    assert rows[2].deaths_occurred is True
    assert rows[2].deaths_count == 1
    assert rows[3].injuries_occurred is False


def test_community_comes_from_the_label_with_a_trailing_space(tmp_path):
    _session, _result, rows = ingest_export(tmp_path)

    assert rows[1].community == "Matelot"


def test_a_clean_export_reports_no_warnings(tmp_path):
    _session, result, _rows = ingest_export(tmp_path)

    assert result.warnings == []


def test_date_filter_includes_the_whole_of_date_to(tmp_path):
    session, _result, _rows = ingest_export(tmp_path)

    stmt = apply_common_filters(
        select(FieldObservation), {"date_from": "2021-04-19", "date_to": "2021-04-22"}
    )

    assert sorted(r.object_id for r in session.scalars(stmt)) == [1, 2]


def test_normalize_headers_strips_and_numbers_repeats():
    assert normalize_headers(["﻿ObjectID", "Community ", "Other Agency ", "Other Agency ", "Community"]) == [
        "﻿ObjectID",
        "Community",
        "Other Agency",
        "Other Agency_2",
        "Community_2",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4/21/2021 3:36:49 PM", datetime(2021, 4, 21, 15, 36, 49, tzinfo=timezone.utc)),
        ("12/5/2022 11:02 AM", datetime(2022, 12, 5, 11, 2, tzinfo=timezone.utc)),
        # ISO without an offset is a Trinidad wall-clock reading.
        ("2024-06-01T09:00:00", datetime(2024, 6, 1, 13, 0, tzinfo=timezone.utc)),
        ("2024-06-01T09:00:00+00:00", datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)),
        ("", None),
    ],
)
def test_parse_timestamp(raw, expected):
    assert parse_timestamp(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4/19/2021 4:00:00 PM", date(2021, 4, 19)),
        ("4/19/2021", date(2021, 4, 19)),
        ("2024-06-01T00:00:00", date(2024, 6, 1)),
        ("2024-06-01", date(2024, 6, 1)),
    ],
)
def test_parse_calendar_date(raw, expected):
    assert parse_calendar_date(raw) == expected


def test_unknown_date_format_names_both_accepted_formats(tmp_path):
    from app.modules.survey123.ingest import IngestFormatError, parse_row

    with pytest.raises(IngestFormatError) as err:
        parse_row({"ObjectID": "1", "GlobalID": "g", "Date of Event": "19 April 2021"}, "salt")

    assert "4/21/2021 3:36:49 PM" in err.value.detail
    assert "ISO-8601" in err.value.detail


def test_missing_expected_column_is_reported(tmp_path):
    session = make_session(tmp_path)
    path = tmp_path / "thin.csv"
    path.write_text("ObjectID,GlobalID,Did any injuries occur?\n1,g1,maybe\n", encoding="utf-8")

    result = ingest_csv(path, session, salt="s")

    assert any("'Community'" in w for w in result.warnings)
    assert any("'maybe'" in w for w in result.warnings)


def test_community_falls_back_to_the_newer_community_question():
    from app.modules.survey123.ingest import parse_row

    fields = parse_row({"ObjectID": "1", "GlobalID": "g", "Community": "", "Community_2": "Morvant"}, "salt")

    assert fields["community"] == "Morvant"
