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


def make_client(monkeypatch, llm_responses: list[str] | None = None) -> TestClient:
    import app.core.report_models  # noqa: F401
    import app.modules.capture.models  # noqa: F401
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401
    import app.modules.whatsapp.models  # noqa: F401

    monkeypatch.setattr(
        "app.api.capture.get_llm_client",
        lambda purpose="batch": FakeLLMClient(responses=llm_responses or [EXTRACT_JSON]),
    )
    Base.metadata.create_all(db_engine)
    return TestClient(create_app())


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


def create_capture(client: TestClient, event_id: int) -> dict:
    response = client.post(
        "/capture/sessions",
        json={"corporation": CORP, "event_id": event_id},
    )
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
