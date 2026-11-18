"""Each test replays a failure seen in the Nov 16 2026 corp UAT transcripts."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from app.db import engine as db_engine

from app.modules.capture.guards import dates_in, echoes_clerk
from app.modules.capture.missing import missing_fields
from app.modules.capture.schemas import (
    CaptureIncident,
    CaptureLog,
    CaptureWorkingSet,
    clean_place,
)
from app.modules.capture.turn import follow_up_text, run_turn

TODAY = date(2026, 11, 16)
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _release_db():
    # The withdraw test opens pooled SQLite connections; later tests delete
    # dev.db and would otherwise write through a stale handle.
    db_engine.dispose()
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


class SequenceLLM:
    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        return self.responses.pop(0)


def reply(message: str, **capture) -> str:
    return json.dumps({"assistant_message": message, "capture": capture})


def working(**fields) -> CaptureWorkingSet:
    return CaptureWorkingSet(as_at=datetime(2026, 11, 16, 10, 0), **fields)


def flood(row_id: str, **fields) -> CaptureIncident:
    return CaptureIncident(row_id=row_id, incident_type="flooding_", **fields)


# Point Fortin: the filing showed Alert Level "None" while the level was red.
def test_alert_wording_none_is_blank_and_a_new_chat_alert_replaces_typed_wording():
    previous = working(alert_detail="None", manual_fields=["alert_detail"])
    assert previous.alert_detail is None

    llm = SequenceLLM(
        reply(
            "Alert level updated to red.",
            alert_level="red",
            alert_detail="Adverse Weather Red Level #1",
            incidents=[],
            logs=[],
        )
    )
    done = run_turn(previous, [], "Adverse Weather Red Level #1", llm)

    assert done.working.alert_level == "red"
    assert done.working.alert_detail == "Adverse Weather Red Level #1"
    assert "alert_detail" not in done.working.manual_fields


def test_alert_level_follows_the_alert_wording():
    assert working(alert_detail="Flood Alert #1 - yellow level").alert_level == "yellow"
    assert working(alert_level="yellow", alert_detail="Alert discontinued").alert_level == (
        "discontinued"
    )


# Couva: "No relief distributed" typed into the alert box became the Alert Level.
def test_alert_wording_that_is_not_an_alert_is_flagged():
    gaps = missing_fields(working(alert_detail="No relief distributed"))

    assert any(item.path == "alert_detail" for item in gaps)


# Siparia: a Nov 16 report was stamped with Oct 4 from an earlier report.
def test_a_new_incident_gets_no_date_the_message_did_not_give():
    previous = working(incidents=[flood("1", community="Fullerton", event_date="2026-10-04")])
    llm = SequenceLLM(
        reply(
            "Captured Cedros flooding.",
            incidents=[
                flood("1", community="Fullerton", event_date="2026-10-04").model_dump(),
                flood("2", community="Cedros", event_date="2026-10-04").model_dump(),
            ],
            logs=[],
        )
    )
    done = run_turn(previous, [], "At least 14 houses affected in Cedros.", llm)

    cedros = next(row for row in done.working.incidents if row.community == "Cedros")
    assert cedros.event_date is None
    # The clerk asks for the date instead of noting it left it blank.
    assert any(
        q.startswith("What day did") and "Cedros" in q for q in done.questions
    )


def test_a_date_the_officer_states_is_accepted():
    previous = working(incidents=[flood("1", community="Cedros")])
    llm = SequenceLLM(
        reply(
            "Captured incident date.",
            incidents=[flood("1", community="Cedros", event_date="2026-11-16").model_dump()],
            logs=[],
        )
    )
    done = run_turn(previous, [], "16th November 2026", llm)

    assert done.working.incidents[0].event_date == "2026-11-16"


def test_dates_in_reads_the_forms_officers_use():
    assert date(2026, 11, 16) in dates_in("16th November 2026", TODAY)
    assert date(2026, 11, 16) in dates_in("Flooding occurred on 16/11/2026", TODAY)
    assert date(2026, 11, 16) in dates_in("On novemer 16, 2026 gasparillo", TODAY)
    assert date(2026, 11, 16) in dates_in("flooding today", TODAY)
    assert date(2026, 11, 15) in dates_in("since yesterday", TODAY)
    assert dates_in("At least 14 houses affected", TODAY) == set()


# Chaguanas and Siparia: rows vanished when the model rewrote the working set.
def test_a_row_the_model_drops_is_kept_and_the_officer_is_told():
    previous = working(
        incidents=[flood("1", community="Fullerton")],
        logs=[CaptureLog(row_id="1", category="resource", statement="Sandbags requested by households")],
    )
    llm = SequenceLLM(
        reply(
            "Captured 50 sandbags on site.",
            incidents=[flood("1", community="Fullerton").model_dump()],
            logs=[{"category": "relief_distributed", "statement": "50 sandbags being distributed", "quantity": 50}],
        )
    )
    done = run_turn(previous, [], "Sandbags on site are 50 and are being distributed.", llm)

    statements = [log.statement for log in done.working.logs]
    assert "Sandbags requested by households" in statements
    assert "50 sandbags being distributed" in statements
    # The new log did not take the dropped row's id.
    assert len({log.row_id for log in done.working.logs}) == 2
    assert any("I kept log 1" in note for note in done.notes)


def test_a_row_the_officer_asks_to_remove_goes():
    previous = working(incidents=[flood("1", community="Fullerton"), flood("2", community="Cedros")])
    llm = SequenceLLM(
        reply(
            "Removed incident 2.",
            incidents=[flood("1", community="Fullerton").model_dump()],
            logs=[],
        )
    )
    done = run_turn(previous, [], "Remove incident 2, it was a duplicate.", llm)

    assert [row.row_id for row in done.working.incidents] == ["1"]


# Chaguanas: "I could not read that update" lost the blown-off roof.
def test_unreadable_reply_is_retried_once():
    llm = SequenceLLM(
        "Sure! Here is the update: {broken",
        reply(
            "Captured a blown-off roof.",
            incidents=[{"incident_type": "blown off roof", "community": "Enterprise"}],
            logs=[],
        ),
    )
    done = run_turn(working(), [], "Reports coming in of one blown off roof at 1:30 pm", llm)

    assert done.parse_ok is True
    assert done.retried is True
    assert done.working.incidents[0].incident_type == "blown_off_roof"
    assert "previous reply could not be parsed" in llm.calls[1][0]


def test_json_after_preamble_parses_without_a_retry():
    llm = SequenceLLM(
        "Here you go:\n"
        + reply("Captured.", incidents=[{"incident_type": "fire", "community": "Arima"}], logs=[])
    )
    done = run_turn(working(), [], "Fire in Arima", llm)

    assert done.retried is False
    assert done.working.incidents[0].community == "Arima"


# San Fernando, Sangre Grande, Point Fortin: "no injuries confirmed" became 0.
def test_no_injuries_confirmed_is_not_a_count_of_zero():
    llm = SequenceLLM(
        reply(
            "Captured flooding.",
            incidents=[flood("1", community="Marabella", injuries_occurred=False, injuries_count=0).model_dump()],
            logs=[],
        )
    )
    done = run_turn(working(), [], "Flooding in Marabella. No injuries have been confirmed.", llm)

    incident = done.working.incidents[0]
    assert incident.injuries_occurred is False
    assert incident.injuries_count is None


def test_an_explicit_zero_stands():
    llm = SequenceLLM(
        reply(
            "Captured.",
            incidents=[flood("1", community="Marabella", injuries_count=0).model_dump()],
            logs=[],
        )
    )
    done = run_turn(working(), [], "Flooding in Marabella, 0 injuries.", llm)

    assert done.working.incidents[0].injuries_count == 0


# Port of Spain, Sangre Grande, Point Fortin: descriptions stored as places.
def test_place_descriptions_are_not_places():
    assert clean_place("low-lying community") is None
    assert clean_place("Unnamed road") is None
    assert clean_place("a community in your corporation") is None
    assert clean_place("Coalmine area") == "Coalmine"
    assert clean_place("Bynoe Trace") == "Bynoe Trace"
    gaps = missing_fields(working(incidents=[flood("1", community="the area")]))
    assert any(item.path == "incidents[0].community" for item in gaps)


# Point Fortin: the clerk said the alert wording was set; it was pinned and wasn't.
def test_a_typed_value_the_model_tried_to_change_is_reported():
    previous = working(present_activity="Assessments ongoing", manual_fields=["present_activity"])
    llm = SequenceLLM(
        reply(
            "Updated present activity.",
            present_activity="Tarpaulin requested at Bynoe Trace",
            incidents=[],
            logs=[],
        )
    )
    done = run_turn(previous, [], "request for a tarpaulin at bynoe trace", llm)

    assert done.working.present_activity == "Assessments ongoing"
    assert any("Present activity was typed in the form" in note for note in done.notes)
    assert done.messages[-1].content == follow_up_text(done)
    assert done.messages[-1].content.startswith(" ".join(done.notes))


def test_claiming_a_capture_that_changed_nothing_is_corrected():
    llm = SequenceLLM(reply("Captured the update.", incidents=[], logs=[]))
    done = run_turn(working(), [], "ok thanks", llm)

    assert done.notes[0] == "Nothing in the report changed from that message."


# Point Fortin pasted the clerk's own confirmation back as a report.
def test_pasted_clerk_text_is_flagged_to_the_model():
    previous_reply = "Captured a new flooding incident in Tom Village affecting 55 people."
    assert echoes_clerk(
        "Captured a new flooding incident in Tom Village along with 2 fallen trees.",
        [previous_reply],
    )
    assert not echoes_clerk("Flooding at Union Road, Marabella.", [previous_reply])


# Point Fortin: "10 marooned" went into special_needs_occupants.
def test_impact_counts_have_their_own_fields_and_reach_the_filing():
    from app.modules.capture.facts import assemble_working_set_facts

    incidents = [
        flood(
            "1",
            incident_scope="area",
            community="Tom Village",
            street="St. Paul Lane",
            households_affected=24,
            persons_affected=55,
            persons_marooned=10,
            access_blocked=True,
        )
    ]
    facts = assemble_working_set_facts(
        working(incidents=incidents), corporation="point_fortin_borough_corporatio", event_id=1
    )

    totals = {f.scope["measure"]: f.value for f in facts if f.metric == "impact_summary"}
    assert totals == {"households_affected": 24, "persons_affected": 55, "persons_marooned": 10}
    register = next(f for f in facts if f.metric == "incident_register")
    assert register.scope["affected"] == (
        "24 households · 55 persons affected · 10 marooned · access blocked"
    )


def test_household_incident_needs_a_house_number():
    gaps = missing_fields(
        working(incidents=[flood("1", incident_scope="household", street="Saddle Road")])
    )
    assert any(item.path == "incidents[0].house_number" for item in gaps)


# Siparia: an empty "+ Add manually" log reached the filing as "[other]".
def test_blank_rows_stay_in_the_draft_but_not_the_filing():
    draft = working(
        incidents=[CaptureIncident(row_id="1")],
        logs=[CaptureLog(row_id="1", statement="")],
    )
    filed = draft.without_blank_rows()

    assert len(draft.incidents) == 1 and len(draft.logs) == 1
    assert filed.incidents == [] and filed.logs == []
    assert missing_fields(draft) == [
        item for item in missing_fields(draft) if not item.path.startswith("incidents[")
    ]


# Siparia: the model must not set the as-at time; the system owns it.
def test_model_cannot_move_the_as_at_time():
    previous = working()
    llm = SequenceLLM(
        json.dumps(
            {
                "assistant_message": "Captured.",
                "capture": {"as_at": "2026-10-04T08:00:00", "incidents": [], "logs": []},
            }
        )
    )
    done = run_turn(previous, [], "update", llm)

    assert done.working.as_at == previous.as_at


def test_filing_shows_impact_totals_affected_column_and_none_reported():
    from pathlib import Path

    from app.core.llm import FakeLLMClient
    from app.modules.capture.sitrep import generate_working_set_sitrep
    from app.templates.loader import load_template

    template = load_template(
        Path(__file__).parent.parent
        / "app/templates/definitions/corp_situation_report.yaml"
    )
    report = generate_working_set_sitrep(
        working(
            alert_detail="Adverse Weather Alert #1 - Yellow Level",
            incidents=[
                flood(
                    "1",
                    incident_scope="area",
                    community="Enterprise",
                    street="Bynoe Trace",
                    event_date="2026-11-16",
                    incident_summary="Main access blocked",
                    households_affected=24,
                    access_blocked=True,
                    injuries_occurred=False,
                ),
                CaptureIncident(
                    row_id="2",
                    incident_scope="household",
                    incident_type="blown_off_roof",
                    community="Enterprise",
                    street="Bynoe Trace",
                    house_number="LP 12",
                    event_date="2026-11-16",
                    incident_summary="Roof blown off",
                ),
            ],
            logs=[CaptureLog(row_id="1", statement="Tarpaulin requested", item="tarpaulin 16x20", quantity=2)],
        ),
        corporation="chaguanas_borough_corporation",
        event_id=1,
        hazard_type="flood",
        report_number=1,
        template=template,
        llm_client=FakeLLMClient(),
        request_id="uat",
    )
    final = report.final_markdown or report.markdown

    assert "## Impact" in final
    assert "| Households affected | 24 |" in final
    assert "24 households · access blocked" in final
    assert "None reported" in final
    assert "Enterprise / LP 12 Bynoe Trace" in final
    assert "**Alert Level:** Adverse Weather Alert #1 - Yellow Level" in final
    # A log with no unit shows no unit, not "units".
    assert "| tarpaulin 16x20 | 2 |" in final


def test_csv_round_trip_keeps_scope_and_counts():
    from app.modules.capture.file import incident_to_csv_row
    from app.modules.sitreps.parse import parse_incident_row

    row = incident_to_csv_row(
        flood(
            "3",
            incident_scope="household",
            community="Maraval",
            street="Saddle Road",
            house_number="#30",
            event_date="2026-11-16",
            households_affected=1,
            persons_affected=4,
            persons_displaced=4,
            access_blocked=False,
            injuries_occurred=False,
            deaths_occurred=False,
            relief_supplied=False,
            forwarded_to_agency=False,
            further_assessment_required=True,
            other_follow_up=False,
        )
    )
    fields, error = parse_incident_row(row, 1)

    assert error is None
    assert fields["incident_scope"] == "household"
    assert fields["house_number"] == "#30"
    assert fields["persons_displaced"] == 4
    assert fields["access_blocked"] is False


def test_old_csv_without_new_columns_still_parses():
    from app.modules.sitreps.parse import parse_incident_row

    fields, error = parse_incident_row(
        {
            "Row ID": "1",
            "Date of Event": "2026-11-16",
            "Incident Type": "flooding",
            "Injuries Occurred": "no",
            "Deaths Occurred": "no",
            "Relief Supplied": "no",
            "Forwarded To Agency": "no",
            "Further Assessment Required": "no",
            "Other Follow Up": "no",
        },
        1,
    )

    assert error is None
    assert fields["incident_scope"] is None and fields["households_affected"] is None


def test_withdrawing_a_test_filing_keeps_its_transcript(monkeypatch):
    from fastapi.testclient import TestClient

    from app import create_app
    from app.db import Base, SessionLocal, engine
    from app.modules.capture.models import CaptureSession
    from app.modules.sitreps.models import SitrepIncident, Submission
    from app.modules.sitreps.withdraw import plan_withdrawal, withdraw_submission
    from tests.test_api_capture import EXTRACT_JSON, _SitrepAwareLLM

    monkeypatch.setattr(
        "app.api.capture.get_llm_client",
        lambda purpose="batch": _SitrepAwareLLM(responses=[EXTRACT_JSON]),
    )
    Base.metadata.create_all(engine)
    client = TestClient(create_app())
    event = client.post(
        "/events",
        json={
            "corporation": "point_fortin_borough_corporatio",
            "title": "Fictional flooding",
            "hazard_type": "flood",
            "started_at": "2026-11-16T00:00:00",
        },
    ).json()
    session_id = client.post(
        "/capture/sessions",
        json={"corporation": "point_fortin_borough_corporatio", "event_id": event["id"]},
    ).json()["id"]
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": "Flooding, no injuries."})
    issued = client.post(f"/capture/sessions/{session_id}/issue")
    assert issued.status_code == 201, issued.text
    submission_id = issued.json()["ingest"]["submission_id"]

    db = SessionLocal()
    plan = plan_withdrawal(db, submission_id)
    assert plan is not None and plan.report_ids and plan.incident_ids
    withdraw_submission(db, plan)

    assert db.get(Submission, submission_id) is None
    assert db.query(SitrepIncident).count() == 0
    kept = db.get(CaptureSession, session_id)
    assert kept.status == "withdrawn" and kept.submission_id is None
    db.close()
    transcript = client.get(f"/admin/capture/sessions/{session_id}/transcript")
    assert transcript.status_code == 200
