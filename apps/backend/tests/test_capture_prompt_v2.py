"""Code changes that shipped with corp_capture v2 (staging session 1, Nov 18)."""

import json
from datetime import date

from app.core.llm import FakeLLMClient
from app.modules.capture.facts import _casualty_label
from app.modules.capture.guards import dates_in
from app.modules.capture.missing import missing_fields
from app.modules.capture.questions import incident_label, missing_questions
from app.modules.capture.schemas import CaptureIncident, CaptureWorkingSet
from app.modules.capture.turn import coerce_working_set, run_turn
from app.prompts.evals import evaluate, load_cases, matches

TODAY = date(2026, 11, 18)


def _reply(capture: dict, message: str = "Added it.") -> str:
    return json.dumps({"assistant_message": message, "capture": capture})


# --- a time of day dates an incident today ------------------------------------


def test_a_time_of_day_names_today():
    assert dates_in("Heavy rainfall since 2am", TODAY) == {TODAY}
    assert dates_in("one blown off roof at 1:30 pm", TODAY) == {TODAY}
    assert dates_in("water up to 2 feet, 14 houses", TODAY) == set()


def test_last_night_allows_either_day():
    assert dates_in("flooding since last night", TODAY) == {TODAY, date(2026, 11, 17)}


def test_since_2am_keeps_the_models_date_for_today():
    reply = _reply(
        {
            "incidents": [
                {"row_id": "1", "community": "Enterprise", "street": "Ramsaran Street",
                 "incident_type": "flooding", "incident_summary": "Flooding.",
                 "event_date": TODAY.isoformat()}
            ]
        }
    )
    done = run_turn(
        CaptureWorkingSet(), [], "Flooding in Enterprise along Ramsaran Street since 2am",
        FakeLLMClient(responses=[reply]), system_prompt="x", today=TODAY,
    )

    assert done.working.incidents[0].event_date == TODAY.isoformat()
    assert "dates_reverted" not in done.interventions


# --- the clerk's questions come from code, after the turn -----------------------


def test_opening_message_gets_questions_about_what_is_still_missing():
    """Chaguanas, Nov 18: two dates and a casualty answer open, nothing asked."""
    reply = _reply(
        {
            "alert_level": "orange",
            "alert_detail": "orange level flood alert",
            "incidents": [
                {"row_id": "1", "incident_scope": "area", "community": "Enterprise",
                 "street": "Ramsaran Street", "incident_type": "flooding",
                 "incident_summary": "12 houses flooded.", "households_affected": 12},
            ],
        }
    )
    done = run_turn(
        CaptureWorkingSet(), [], "Orange level flood alert. Flooding in Enterprise along Ramsaran Street, 12 houses.",
        FakeLLMClient(responses=[reply]), system_prompt="x", today=TODAY,
    )

    assert done.questions == [
        "What day did the flooding at Ramsaran Street happen?",
        "Were there any injuries or deaths at the flooding at Ramsaran Street?",
    ]
    assert done.messages[-1].content.endswith(done.questions[-1])


def test_questions_group_incidents_and_stop_at_two():
    working = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", community="Enterprise", street="Ramsaran Street", incident_type="flooding_"),
            CaptureIncident(row_id="2", incident_scope="household", community="Charlieville",
                            street="Caroni Savannah Road", house_number="#14", incident_type="blown_off_roof",
                            injuries_occurred=False),
        ]
    )

    questions = missing_questions(missing_fields(working), working)

    assert questions[0] == "Has the Met Office issued an alert for your region, and at what level?"
    assert questions[1] == (
        "What day did the flooding at Ramsaran Street and the blown-off roof at "
        "#14 Caroni Savannah Road happen?"
    )
    assert len(questions) == 2


def test_a_question_just_asked_is_not_repeated_and_the_alert_is_asked_once():
    working = CaptureWorkingSet(
        incidents=[CaptureIncident(row_id="1", community="Gasparillo", incident_type="flooding_", event_date="2026-11-16")]
    )
    missing = missing_fields(working)
    first = missing_questions(missing, working)

    again = missing_questions(missing, working, recently_asked=" ".join(first), asked_before=" ".join(first))

    assert first[0].startswith("Has the Met Office")
    assert again == []
    later = missing_questions(missing, working, recently_asked="", asked_before=" ".join(first))
    assert later == ["Were there any injuries or deaths at the flooding at Gasparillo?"]


def test_an_unplaced_incident_is_named_by_type():
    incident = CaptureIncident(row_id="3", incident_type="blown_off_roof")

    assert incident_label(incident) == "the blown-off roof (incident 3)"


# --- fields the model leaves out keep their value -------------------------------


def test_a_returned_row_keeps_fields_it_left_out():
    previous = CaptureWorkingSet(
        incidents=[
            CaptureIncident(row_id="1", community="Gasparillo", street="Gopaul Ave",
                            incident_type="flooding_", event_date="2026-11-16", access_blocked=True)
        ]
    )

    merged = coerce_working_set(
        {"capture": {"incidents": [{"row_id": "1", "households_affected": 16}]}}, previous
    )

    row = merged.incidents[0]
    assert (row.households_affected, row.access_blocked, row.event_date) == (16, True, "2026-11-16")


def test_an_explicit_null_still_clears_a_field():
    previous = CaptureWorkingSet(
        incidents=[CaptureIncident(row_id="1", community="Gasparillo", incident_type="flooding_", households_affected=16)]
    )

    merged = coerce_working_set(
        {"capture": {"incidents": [{"row_id": "1", "households_affected": None}]}}, previous
    )

    assert merged.incidents[0].households_affected is None


# --- the register says when casualties are unknown ------------------------------


def test_unknown_casualties_read_not_confirmed():
    assert _casualty_label(None, None) == "Not confirmed"
    assert _casualty_label(False, None) == "None reported"
    assert _casualty_label(True, 2) is None


# --- eval matching ------------------------------------------------------------


def test_eval_value_specs():
    assert matches("flooding_", "flooding", TODAY)
    assert matches("2026-11-18", "{today}", TODAY)
    assert matches(None, None, TODAY) and not matches(0, None, TODAY)
    assert matches(12.0, 12, TODAY) and not matches(True, 1, TODAY)
    assert matches("Flood with 2 ft of water", {"any_of": ["2 feet", "2 ft"]}, TODAY)
    assert matches("resource", {"is": "resource"}, TODAY) and not matches("resources", {"is": "resource"}, TODAY)
    assert matches(None, {"present": False}, TODAY) and matches("x", {"present": True}, TODAY)
    assert matches("2026-11-16", {"not": "2026-10-04"}, TODAY)


def test_eval_checks_on_a_working_set():
    working = {
        "alert_level": "orange",
        "incidents": [{"row_id": "1", "street": "Ramsaran Street", "households_affected": 12}],
        "logs": [],
    }

    assert evaluate({"kind": "row", "rows": "incidents", "where": {"street": "ramsaran"},
                     "expect": {"households_affected": 12}}, working, [], True, TODAY).passed
    missing = evaluate({"kind": "row", "rows": "incidents", "where": {"street": "Montrose"},
                        "expect": {"access_blocked": True}}, working, [], True, TODAY)
    assert not missing.passed and missing.detail == "no matching row"
    assert evaluate({"kind": "none", "rows": "logs", "where": {"statement": "impassable"}},
                    working, [], True, TODAY).passed
    assert evaluate({"kind": "asks", "about": "what day"}, working,
                    ["What day did the flooding happen?"], True, TODAY).passed


def test_the_test_set_loads_and_every_check_is_well_formed():
    """Every case runs its checks against an empty result without a spec error."""
    for case in load_cases("corp_capture"):
        for check in case.checks:
            evaluate(check, {"incidents": [], "logs": []}, [], True, case.today)
