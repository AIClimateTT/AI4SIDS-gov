import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.llm import FakeLLMClient
from app.core.registry import reset_registry
from app.db import Base, engine as db_engine
from app.modules.sitreps.module import sitrep_module

CORP = "diego_martin_regional_corporati"
OTHER_CORP = "san_fernando_city_corporation"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"

EXTRACT_JSON = json.dumps(
    {
        "assistant_message": (
            "Captured: 5 houses flooded in Petit Valley, no injuries. "
            "200 sandbags remaining at the depot. What was the date of the flooding?"
        ),
        "capture": {
            "as_at": "2026-08-18T14:00:00",
            "alert_level": "yellow",
            "present_activity": "Adverse weather response",
            "situation_overview": None,
            "incidents": [
                {
                    "row_id": "1",
                    "community": "Petit Valley",
                    "incident_type": "flooding",
                    "incident_summary": "5 houses flooded",
                    "injuries_count": 0,
                    "deaths_count": 0,
                }
            ],
            "logs": [
                {
                    "category": "resource",
                    "statement": "200 sandbags remaining at depot",
                    "item": "sandbags",
                    "quantity": 200,
                    "unit": "bags",
                    "status": "available",
                }
            ],
        },
    }
)

CORRECT_JSON = json.dumps(
    {
        "assistant_message": "Updated: 5 houses flooded in Petit Valley, not 3.",
        "capture": {
            "as_at": "2026-08-18T14:00:00",
            "alert_level": "yellow",
            "incidents": [
                {
                    "row_id": "1",
                    "community": "Petit Valley",
                    "incident_type": "flooding_",
                    "incident_summary": "5 houses flooded",
                    "injuries_count": 0,
                    "deaths_count": 0,
                }
            ],
            "logs": [
                {
                    "category": "resource",
                    "statement": "200 sandbags remaining at depot",
                    "item": "sandbags",
                    "quantity": 200,
                    "unit": "bags",
                    "status": "available",
                }
            ],
        },
    }
)

INVENTED_JSON = json.dumps(
    {
        "assistant_message": "Noted flooding in Petit Valley.",
        "capture": {
            "as_at": "2026-08-18T14:00:00",
            "alert_level": "none",
            "incidents": [
                {
                    "row_id": "1",
                    "community": "Petit Valley",
                    "incident_type": "flooding_",
                    "incident_summary": "houses flooded",
                    "injuries_count": 12,
                }
            ],
            "logs": [],
        },
    }
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "definitions"


class _SitrepAwareLLM(FakeLLMClient):
    """Capture turns get canned JSON; sitrep narration uses FakeLLMClient auto-cite."""

    def generate(self, system_prompt: str, user_content: str) -> str:
        try:
            data = json.loads(user_content)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("facts"), list):
            return FakeLLMClient()._auto_narrative(user_content)
        return super().generate(system_prompt, user_content)


def make_client(monkeypatch, llm_responses: list[str] | None = None) -> TestClient:
    import app.core.report_models  # noqa: F401
    import app.core.template_models  # noqa: F401
    import app.modules.capture.models  # noqa: F401
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401
    import app.modules.whatsapp.models  # noqa: F401

    monkeypatch.setattr(
        "app.api.capture.get_llm_client",
        lambda purpose="batch": _SitrepAwareLLM(responses=llm_responses or [EXTRACT_JSON]),
    )
    Base.metadata.create_all(db_engine)
    return TestClient(create_app())


def install_templates() -> None:
    from sqlalchemy.orm import sessionmaker

    from app.core.template_store import import_template_directory

    db = sessionmaker(bind=db_engine)()
    import_template_directory(TEMPLATES_DIR, db)
    db.close()


def create_event(client: TestClient) -> int:
    created = client.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Adverse Weather August 2026",
            "hazard_type": "flood",
            "started_at": "2026-08-18T00:00:00",
        },
    )
    assert created.status_code == 201
    return created.json()["id"]


def create_capture(client: TestClient, event_id: int | None = None) -> dict:
    payload: dict = {"corporation": CORP}
    if event_id is not None:
        payload["event_id"] = event_id
    response = client.post("/capture/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_session_opens_with_assistant_prompt(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    body = create_capture(client, event_id)

    assert body["status"] == "draft"
    assert body["incidents"] == []
    assert body["logs"] == []
    assert body["messages"][0]["role"] == "assistant"
    assert "incident" in body["messages"][0]["content"].lower()


def test_turn_extracts_incident_and_log(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={
            "message": (
                "Yellow alert. 5 houses flooded in Petit Valley, no injuries. "
                "200 sandbags remaining at depot."
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alert_level"] == "yellow"
    assert body["incidents"][0]["community"] == "Petit Valley"
    assert body["incidents"][0]["incident_type"] == "flooding_"
    assert body["logs"][0]["quantity"] == 200
    assert "5 houses" in body["messages"][-1]["content"]
    assert any("date" in item["message"].lower() for item in body["missing"])


def test_correction_turn_updates_working_set(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON, CORRECT_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "3 houses flooded in Petit Valley. 200 sandbags remaining."},
    )

    response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "wait not 3 houses, 5"},
    )
    body = response.json()
    assert body["incidents"][0]["incident_summary"] == "5 houses flooded"
    assert body["incidents"][0]["incident_summary"] != "3 houses flooded"


def test_invented_quantity_is_dropped(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[INVENTED_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "Flooding in Petit Valley."},
    )
    assert response.json()["incidents"][0]["injuries_count"] is None


def test_put_edit_is_visible_on_next_turn(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )

    updated = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "orange",
            "incidents": [
                {
                    "row_id": "1",
                    "community": "Diego Martin",
                    "incident_type": "flooding_",
                    "incident_summary": "5 houses flooded",
                    "injuries_count": 0,
                    "deaths_count": 0,
                }
            ],
            "logs": [
                {
                    "category": "resource",
                    "statement": "200 sandbags remaining at depot",
                    "item": "sandbags",
                    "quantity": 200,
                    "unit": "bags",
                    "status": "available",
                }
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["alert_level"] == "orange"
    assert updated.json()["incidents"][0]["community"] == "Diego Martin"

    class Recording(FakeLLMClient):
        def __init__(self):
            super().__init__(responses=[EXTRACT_JSON])
            self.seen: list[str] = []

        def generate(self, system_prompt: str, user_content: str) -> str:
            self.seen.append(user_content)
            return super().generate(system_prompt, user_content)

    recorder = Recording()
    monkeypatch.setattr("app.api.capture.get_llm_client", lambda purpose="batch": recorder)
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "That is all for now."},
    )
    assert "Diego Martin" in recorder.seen[0]
    assert "orange" in recorder.seen[0]


def test_file_creates_submission_rows_metrics_can_see(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )

    response = client.post(f"/capture/sessions/{session_id}/file")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session"]["status"] == "filed"
    assert body["ingest"]["incidents_inserted"] == 1
    assert body["ingest"]["logs_inserted"] == 1

    from sqlalchemy.orm import sessionmaker

    from app.modules.sitreps.models import SitrepIncident

    Session = sessionmaker(bind=db_engine)
    db = Session()
    facts = sitrep_module.run_metric(
        "incident_count",
        {
            "corporation": CORP,
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        },
        db,
    )
    db.close()
    assert facts[0].value == 1
    db = Session()
    assert db.query(SitrepIncident).count() == 1
    db.close()


def test_zero_row_file_succeeds(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    response = client.post(f"/capture/sessions/{session_id}/file")
    assert response.status_code == 201, response.text
    assert response.json()["ingest"]["incidents_inserted"] == 0
    assert response.json()["ingest"]["logs_inserted"] == 0
    assert response.json()["session"]["status"] == "filed"


def test_csv_submissions_still_work(monkeypatch):
    import io

    client = make_client(monkeypatch)
    event_id = create_event(client)
    incidents = "Row ID,Incident Type,Date of Event\n1,fallen_tree,2026-08-18\n"
    response = client.post(
        "/submissions",
        data={
            "corporation": CORP,
            "as_at": "2026-08-18T16:00:00",
            "alert_level": "none",
            "event_id": event_id,
        },
        files={
            "incidents_file": ("incidents.csv", io.BytesIO(incidents.encode()), "text/csv"),
        },
    )
    assert response.status_code == 201
    assert response.json()["incidents_inserted"] == 1


def test_capture_turn_requests_the_chat_llm(monkeypatch):
    seen: list[str] = []

    def fake_get(purpose: str = "batch"):
        seen.append(purpose)
        return FakeLLMClient(responses=[EXTRACT_JSON])

    import app.core.report_models  # noqa: F401
    import app.modules.capture.models  # noqa: F401
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401
    import app.modules.whatsapp.models  # noqa: F401

    monkeypatch.setattr("app.api.capture.get_llm_client", fake_get)
    Base.metadata.create_all(db_engine)
    client = TestClient(create_app())
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley."},
    )
    assert seen == ["chat"]


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_stream_turn_emits_text_then_capture_updated(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    with client.stream(
        "POST",
        f"/capture/sessions/{session_id}/turns/stream",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Yellow alert. 5 houses flooded in Petit Valley, no injuries. "
                        "200 sandbags remaining at depot."
                    ),
                }
            ],
            "data": {"session_id": session_id},
        },
    ) as response:
        assert response.status_code == 200, response.read()
        events = _parse_sse("".join(response.iter_text()))

    types = [event["type"] for event in events]
    assert types[0] == "RUN_STARTED"
    assert "TEXT_MESSAGE_START" in types
    assert "TEXT_MESSAGE_CONTENT" in types
    assert "TEXT_MESSAGE_END" in types
    assert "CUSTOM" in types
    assert types[-1] == "RUN_FINISHED"

    deltas = "".join(
        event["delta"] for event in events if event["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "5 houses" in deltas

    custom = next(event for event in events if event["type"] == "CUSTOM")
    assert custom["name"] == "capture.updated"
    snapshot = custom["value"]
    assert snapshot["alert_level"] == "yellow"
    assert snapshot["incidents"][0]["community"] == "Petit Valley"
    assert snapshot["logs"][0]["quantity"] == 200
    assert any("date" in item["message"].lower() for item in snapshot["missing"])

    stored = client.get(f"/capture/sessions/{session_id}").json()
    assert stored["incidents"][0]["community"] == "Petit Valley"


def test_stream_turn_drops_invented_numbers(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[INVENTED_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    with client.stream(
        "POST",
        f"/capture/sessions/{session_id}/turns/stream",
        json={
            "messages": [{"role": "user", "content": "Flooding in Petit Valley."}],
        },
    ) as response:
        events = _parse_sse("".join(response.iter_text()))

    custom = next(event for event in events if event["type"] == "CUSTOM")
    assert custom["value"]["incidents"][0]["injuries_count"] is None


def test_non_stream_turn_still_works_after_stream_endpoint(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )
    assert response.status_code == 200
    assert response.json()["incidents"][0]["community"] == "Petit Valley"


def test_put_session_records_manual_fields(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    response = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["manual_fields"] == ["alert_level"]

    reread = client.get(f"/capture/sessions/{session_id}")
    assert reread.json()["manual_fields"] == ["alert_level"]


def test_manual_edit_survives_a_model_turn_end_to_end(monkeypatch):
    """The whole point of this task: an officer's hand-edit, persisted through
    the HTTP PUT, must survive a subsequent model turn that tries to
    overwrite it, and must still be readable (with provenance) after that."""
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    put_response = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert put_response.status_code == 200, put_response.text
    assert put_response.json()["alert_level"] == "red"
    assert put_response.json()["manual_fields"] == ["alert_level"]

    # EXTRACT_JSON's capture payload sets alert_level to "yellow" — a model
    # turn that would normally clobber the officer's manual "red" choice.
    turn_response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley, no injuries."},
    )
    assert turn_response.status_code == 200, turn_response.text
    assert turn_response.json()["alert_level"] == "red"
    assert turn_response.json()["manual_fields"] == ["alert_level"]

    reread = client.get(f"/capture/sessions/{session_id}")
    assert reread.json()["alert_level"] == "red"
    assert reread.json()["manual_fields"] == ["alert_level"]


def test_put_omitting_manual_fields_leaves_provenance_unchanged(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    first = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["manual_fields"] == ["alert_level"]

    # No manual_fields key at all in this body — omission, not an empty list.
    second = client.put(
        f"/capture/sessions/{session_id}",
        json={"alert_level": "red", "incidents": [], "logs": []},
    )
    assert second.status_code == 200, second.text
    assert second.json()["manual_fields"] == ["alert_level"]

    reread = client.get(f"/capture/sessions/{session_id}")
    assert reread.json()["manual_fields"] == ["alert_level"]


def test_put_explicit_empty_manual_fields_clears_provenance(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    first = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["manual_fields"] == ["alert_level"]

    # An explicit empty list is a deliberate clear, e.g. the officer reverted
    # their edit — this must NOT be treated the same as omission.
    second = client.put(
        f"/capture/sessions/{session_id}",
        json={"alert_level": "red", "incidents": [], "logs": [], "manual_fields": []},
    )
    assert second.status_code == 200, second.text
    assert second.json()["manual_fields"] == []

    reread = client.get(f"/capture/sessions/{session_id}")
    assert reread.json()["manual_fields"] == []


def test_omitting_manual_fields_on_put_still_protects_a_later_model_turn(monkeypatch):
    """The scenario that matters: an officer marks a field manual, later PUTs
    an update that doesn't mention manual_fields at all (e.g. a client that
    only patches incidents/logs), and a subsequent model turn must still be
    unable to clobber the officer's earlier value."""
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON])
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]

    first = client.put(
        f"/capture/sessions/{session_id}",
        json={
            "alert_level": "red",
            "incidents": [],
            "logs": [],
            "manual_fields": ["alert_level"],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["manual_fields"] == ["alert_level"]

    # Second PUT omits manual_fields entirely.
    second = client.put(
        f"/capture/sessions/{session_id}",
        json={"alert_level": "red", "incidents": [], "logs": []},
    )
    assert second.status_code == 200, second.text
    assert second.json()["manual_fields"] == ["alert_level"]

    # EXTRACT_JSON sets alert_level to "yellow" — must not win against the
    # still-active manual pin on "alert_level".
    turn_response = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley, no injuries."},
    )
    assert turn_response.status_code == 200, turn_response.text
    assert turn_response.json()["alert_level"] == "red"
    assert turn_response.json()["manual_fields"] == ["alert_level"]


def test_session_can_start_with_no_event(monkeypatch):
    client = make_client(monkeypatch)
    assert create_capture(client)["event_id"] is None


def test_sessions_list_without_event_filter(monkeypatch):
    client = make_client(monkeypatch)
    create_capture(client)
    response = client.get("/capture/sessions", params={"corporation": CORP})
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_filing_incidents_without_an_event_is_rejected(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    client.put(
        f"/capture/sessions/{session_id}",
        json={
            "incidents": [{"row_id": "1", "incident_summary": "5 houses flooded"}],
            "logs": [],
        },
    )
    response = client.post(f"/capture/sessions/{session_id}/file")
    assert response.status_code == 400
    assert "event" in response.json()["detail"]


def test_filing_logs_only_without_an_event_is_allowed(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    client.put(
        f"/capture/sessions/{session_id}",
        json={
            "incidents": [],
            "logs": [
                {"row_id": "1", "statement": "200 sandbags in stock", "category": "resource"}
            ],
        },
    )
    assert client.post(f"/capture/sessions/{session_id}/file").status_code == 201


def test_event_less_create_reuses_the_same_draft(monkeypatch):
    """Design decision: a second event-less create for the same corporation
    must hand back the SAME draft, not start a fresh conversation. This is
    intended to stop abandoned drafts piling up during a storm; the UI offers
    a 'resume' affordance for it. Pinned explicitly so it cannot regress."""
    client = make_client(monkeypatch)
    first = create_capture(client)
    second = create_capture(client)
    assert first["id"] == second["id"]


def test_event_less_draft_and_event_attached_draft_do_not_collide(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)

    event_less = create_capture(client)
    with_event = create_capture(client, event_id)
    assert event_less["id"] != with_event["id"]

    # Creating again with no event must return the event-less draft, not the
    # one attached to an event.
    again_event_less = create_capture(client)
    assert again_event_less["id"] == event_less["id"]

    # Creating again with the event must return the event-attached draft, not
    # the event-less one.
    again_with_event = create_capture(client, event_id)
    assert again_with_event["id"] == with_event["id"]


def test_attach_existing_event_to_a_session(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": event_id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["event_id"] == event_id


def test_attach_creates_a_new_event_when_given_details(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event",
        json={
            "title": "August flooding",
            "hazard_type": "flood",
            "started_at": "2026-08-18T00:00:00",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["event_id"] is not None

    events = client.get("/events", params={"corporation": CORP}).json()
    assert any(item["title"] == "August flooding" for item in events)


def test_attach_requires_one_of_the_two_branches(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client)["id"]
    assert client.post(f"/capture/sessions/{session_id}/event", json={}).status_code == 400


def test_attach_rejects_an_event_owned_by_another_corporation(monkeypatch):
    client = make_client(monkeypatch)
    other = client.post(
        "/events",
        json={
            "corporation": OTHER_CORP,
            "title": "Someone else's storm",
            "hazard_type": "flood",
            "started_at": "2026-08-18T00:00:00",
        },
    ).json()["id"]
    session_id = create_capture(client)["id"]

    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": other}
    )
    assert response.status_code == 404


def test_reattach_replaces_event_and_leaves_captured_data_untouched(monkeypatch):
    """Design decision: re-attaching a different event to a session that
    already has one is ALLOWED while the session is still a draft. Nothing has
    been written to the submission tables yet, so an officer who picked the
    wrong event must be able to correct it before filing. The event_id must
    be replaced outright, and the incidents/logs captured so far must be left
    exactly as they were — re-attach only changes which event the eventual
    filing will be scoped to."""
    client = make_client(monkeypatch)
    first_event = create_event(client)
    session_id = create_capture(client, first_event)["id"]

    turn = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={
            "message": (
                "5 houses flooded in Petit Valley, no injuries. "
                "200 sandbags remaining at depot."
            )
        },
    )
    assert turn.status_code == 200, turn.text
    incidents_before = turn.json()["incidents"]
    logs_before = turn.json()["logs"]
    assert incidents_before and logs_before

    second_event = client.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "A different storm",
            "hazard_type": "wind",
            "started_at": "2026-08-19T00:00:00",
        },
    ).json()["id"]
    assert second_event != first_event

    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": second_event}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["event_id"] == second_event
    assert body["event_id"] != first_event
    assert body["incidents"] == incidents_before
    assert body["logs"] == logs_before

    reread = client.get(f"/capture/sessions/{session_id}").json()
    assert reread["event_id"] == second_event
    assert reread["incidents"] == incidents_before
    assert reread["logs"] == logs_before


def test_attach_is_rejected_once_the_session_is_filed(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    filed = client.post(f"/capture/sessions/{session_id}/file")
    assert filed.status_code == 201, filed.text

    other_event = create_event(client)
    response = client.post(
        f"/capture/sessions/{session_id}/event", json={"event_id": other_event}
    )
    assert response.status_code == 409


def test_preview_does_not_ingest_incidents(monkeypatch):
    client = make_client(monkeypatch)
    install_templates()
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )
    response = client.post(f"/capture/sessions/{session_id}/preview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["submission_id"] is None
    assert body["sitrep"]["markdown"]
    assert body["sitrep"]["stale"] is False
    from sqlalchemy.orm import sessionmaker

    from app.modules.sitreps.models import SitrepIncident

    db = sessionmaker(bind=db_engine)()
    assert db.query(SitrepIncident).count() == 0
    db.close()


def test_issue_ingests_and_persists_a_report(monkeypatch):
    client = make_client(monkeypatch)
    install_templates()
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley."},
    )
    response = client.post(f"/capture/sessions/{session_id}/issue")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session"]["status"] == "filed"
    assert body["session"]["report_id"]
    assert body["ingest"]["incidents_inserted"] == 1
    report = client.get(f"/reports/{body['session']['report_id']}")
    assert report.status_code == 200
    assert "[C001]" in report.json()["markdown"]


def test_issue_rejects_incidents_without_an_event(monkeypatch):
    client = make_client(monkeypatch)
    session_id = create_capture(client, event_id=None)["id"]
    client.put(
        f"/capture/sessions/{session_id}",
        json={
            "incidents": [{"row_id": "1", "incident_summary": "5 houses flooded"}],
            "logs": [],
        },
    )
    response = client.post(f"/capture/sessions/{session_id}/issue")
    assert response.status_code == 400


def test_preview_on_filed_session_is_conflict(monkeypatch):
    client = make_client(monkeypatch)
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(f"/capture/sessions/{session_id}/file")
    assert client.post(f"/capture/sessions/{session_id}/preview").status_code == 409


def test_issue_incident_count_matches_ingested_metric(monkeypatch):
    client = make_client(monkeypatch)
    install_templates()
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley."},
    )
    response = client.post(f"/capture/sessions/{session_id}/issue")
    assert response.status_code == 201, response.text
    submission_id = response.json()["session"]["submission_id"]

    from sqlalchemy.orm import sessionmaker

    from app.modules.capture.facts import assemble_working_set_facts
    from app.modules.capture.store import get_session_row, working_set_from_session

    db = sessionmaker(bind=db_engine)()
    row = get_session_row(db, session_id)
    working = working_set_from_session(row)
    working_set_count = next(
        fact.value
        for fact in assemble_working_set_facts(
            working, corporation=row.corporation, event_id=row.event_id
        )
        if fact.metric == "incident_count"
    )
    ingested = sitrep_module.run_metric(
        "incident_count",
        {"corporation": CORP, "submission_id": submission_id},
        db,
    )
    db.close()
    assert ingested[0].value == working_set_count
    assert ingested[0].value == 1


def test_issue_keeps_session_draft_if_generate_fails(monkeypatch):
    client = make_client(monkeypatch)
    install_templates()
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley."},
    )

    def fail_generate(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("app.api.capture.generate_report", fail_generate)
    with pytest.raises(RuntimeError, match="llm down"):
        client.post(f"/capture/sessions/{session_id}/issue")

    stored = client.get(f"/capture/sessions/{session_id}")
    assert stored.status_code == 200, stored.text
    assert stored.json()["status"] == "draft"
    assert stored.json()["report_id"] is None
    assert stored.json()["submission_id"] is None

    from app.core.engine import generate_report as real_generate_report

    monkeypatch.setattr("app.api.capture.generate_report", real_generate_report)
    retry = client.post(f"/capture/sessions/{session_id}/issue")
    assert retry.status_code == 201, retry.text
    assert retry.json()["session"]["status"] == "filed"
    assert retry.json()["session"]["report_id"]


def test_issue_rolls_back_if_session_persist_fails(monkeypatch):
    client = make_client(monkeypatch)
    install_templates()
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )

    def fail_persist(*args, **kwargs):
        raise RuntimeError("session persist failed")

    monkeypatch.setattr("app.api.capture.persist_issued_sitrep", fail_persist)
    with pytest.raises(RuntimeError, match="session persist failed"):
        client.post(f"/capture/sessions/{session_id}/issue")

    stored = client.get(f"/capture/sessions/{session_id}")
    assert stored.json()["status"] == "draft"
    assert stored.json()["report_id"] is None
    assert stored.json()["submission_id"] is None

    from sqlalchemy.orm import sessionmaker

    from app.core.report_models import Report
    from app.modules.sitreps.models import SitrepIncident, SituationLog, Submission

    db = sessionmaker(bind=db_engine)()
    assert db.query(Report).count() == 0
    assert db.query(Submission).count() == 0
    assert db.query(SitrepIncident).count() == 0
    assert db.query(SituationLog).count() == 0
    db.close()

    from app.modules.capture.sitrep import persist_issued_sitrep

    monkeypatch.setattr(
        "app.api.capture.persist_issued_sitrep",
        persist_issued_sitrep,
    )
    retry = client.post(f"/capture/sessions/{session_id}/issue")
    assert retry.status_code == 201, retry.text
    assert retry.json()["session"]["status"] == "filed"
    assert retry.json()["session"]["report_id"]
    assert retry.json()["ingest"]["incidents_inserted"] == 1
    assert retry.json()["ingest"]["logs_inserted"] == 1
