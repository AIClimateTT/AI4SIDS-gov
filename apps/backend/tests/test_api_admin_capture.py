import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.auth.models import User
from app.auth.tokens import create_access_token
from app.db import Base, SessionLocal, engine as db_engine

from tests.test_api_capture import (
    CORP,
    EXTRACT_JSON,
    _SitrepAwareLLM,
    create_capture,
    create_event,
)

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_db():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def make_client(monkeypatch, responses: list[str] | None = None) -> TestClient:
    import app.core.report_models  # noqa: F401
    import app.modules.capture.models  # noqa: F401
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    monkeypatch.setattr(
        "app.api.capture.get_llm_client",
        lambda purpose="batch": _SitrepAwareLLM(responses=responses or [EXTRACT_JSON]),
    )
    Base.metadata.create_all(db_engine)
    return TestClient(create_app())


def _draft_with_turn(client: TestClient) -> tuple[int, int]:
    event_id = create_event(client)
    session_id = create_capture(client, event_id)["id"]
    turn = client.post(
        f"/capture/sessions/{session_id}/turns",
        json={"message": "5 houses flooded in Petit Valley. 200 sandbags remaining."},
    )
    assert turn.status_code == 200, turn.text
    return event_id, session_id


def test_admin_lists_drafts_and_filed_sessions_for_a_corporation(monkeypatch):
    client = make_client(monkeypatch)
    event_id, draft_id = _draft_with_turn(client)

    response = client.get("/admin/capture/sessions", params={"corporation": CORP})

    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["id"] for row in rows] == [draft_id]
    row = rows[0]
    assert row["status"] == "draft"
    assert row["event_id"] == event_id
    assert row["message_count"] == 3
    assert row["officer_message_count"] == 1
    # The list is a register, not a view of the draft's contents.
    assert "incidents" not in row
    assert "messages" not in row


def test_transcript_json_carries_chat_facts_and_sitrep(monkeypatch):
    client = make_client(monkeypatch)
    _event_id, session_id = _draft_with_turn(client)
    preview = client.post(f"/capture/sessions/{session_id}/preview")
    assert preview.status_code == 200, preview.text

    response = client.get(
        f"/admin/capture/sessions/{session_id}/transcript", params={"format": "json"}
    )

    assert response.status_code == 200, response.text
    assert "attachment" in response.headers["content-disposition"]
    assert ".json" in response.headers["content-disposition"]
    body = json.loads(response.content)
    assert body["session"]["id"] == session_id
    assert body["session"]["status"] == "draft"
    assert body["event"]["title"] == "Adverse Weather August 2026"
    assert [m["role"] for m in body["messages"]] == ["assistant", "user", "assistant"]
    assert body["capture"]["incidents"][0]["community"] == "Petit Valley"
    assert body["capture"]["logs"][0]["quantity"] == 200
    assert body["sitrep"]["final_markdown"]
    assert "exported_at" in body


def test_transcript_markdown_reads_as_a_document(monkeypatch):
    client = make_client(monkeypatch)
    _event_id, session_id = _draft_with_turn(client)

    response = client.get(
        f"/admin/capture/sessions/{session_id}/transcript", params={"format": "md"}
    )

    assert response.status_code == 200, response.text
    assert ".md" in response.headers["content-disposition"]
    text = response.text
    assert "## Conversation" in text
    assert "5 houses flooded in Petit Valley" in text
    assert "## Incidents (1)" in text
    assert "## Situation logs (1)" in text
    assert "No sitrep has been generated" in text


def test_transcript_of_unknown_session_is_404(monkeypatch):
    client = make_client(monkeypatch)

    assert client.get("/admin/capture/sessions/999/transcript").status_code == 404


def test_unknown_corporation_is_400(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/admin/capture/sessions", params={"corporation": "nowhere"})

    assert response.status_code == 400


@pytest.mark.real_auth
@pytest.mark.parametrize("role,corporation", [("dmu", None), ("corp", CORP)])
def test_only_admin_can_export_transcripts(monkeypatch, role, corporation):
    Base.metadata.create_all(db_engine)
    db = SessionLocal()
    user = User(
        email=f"{role}@example.com",
        role=role,
        first_name="Test",
        corporation=corporation,
        is_active=True,
    )
    db.add(user)
    db.commit()
    token = create_access_token(user_id=user.user_id, role=user.role, email=user.email)
    db.close()
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers["Authorization"] = f"Bearer {token}"

    listing = client.get("/admin/capture/sessions", params={"corporation": CORP})
    export = client.get("/admin/capture/sessions/1/transcript")

    assert listing.status_code == 403
    assert export.status_code == 403
    Base.metadata.drop_all(db_engine)
