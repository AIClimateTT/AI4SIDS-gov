import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.core.llm import FakeLLMClient
from app.core.registry import reset_registry
from app.db import Base, engine as db_engine

CORP = "diego_martin_regional_corporati"
DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"

EXTRACT_JSON = json.dumps(
    {
        "incidents": [
            {
                "corporation": CORP,
                "community": "Petit Valley",
                "incident_type": "flooding_",
                "incident_summary": "3 houses flooded",
                "event_date": "2026-08-15",
                "source_index": 1,
                "source_quote": "3 houses flooded in Petit Valley",
            }
        ],
        "logs": [
            {
                "corporation": CORP,
                "category": "resource",
                "statement": "200 sandbags remaining at depot",
                "item": "sandbags",
                "quantity": 200,
                "unit": "bags",
                "status": "available",
                "source_index": 2,
                "source_quote": "200 sandbags remaining at depot",
            }
        ],
    }
)

CHAT = (
    "[15/08/2026, 14:32:10] Jane Doe: Diego Martin: 3 houses flooded in Petit Valley\n"
    "[15/08/2026, 14:33:02] John Smith: 200 sandbags remaining at depot\n"
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


def make_client(
    monkeypatch,
    llm_responses: list[str] | None = None,
    llm_client=None,
) -> TestClient:
    import app.core.report_models  # noqa: F401
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401
    import app.modules.whatsapp.models  # noqa: F401

    shared = llm_client or FakeLLMClient(responses=llm_responses or [EXTRACT_JSON])
    monkeypatch.setattr("app.api.whatsapp.get_llm_client", lambda purpose="batch": shared)
    monkeypatch.setattr("app.core.llm.get_llm_client", lambda purpose="batch": shared)
    Base.metadata.create_all(db_engine)
    return TestClient(create_app())


def test_extract_returns_proposals(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/whatsapp/extract",
        files={"file": ("hour.txt", CHAT.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["filename"] == "hour.txt"
    assert body["message_count"] == 2
    assert body["draft_id"] == body["id"]
    assert body["incidents"][0]["incident_summary"] == "3 houses flooded"
    assert body["incidents"][0]["included"] is True
    assert body["logs"][0]["quantity"] == 200
    assert body["status"] == "ready"

    reloaded = client.get(f"/whatsapp/drafts/{body['id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["incidents"][0]["incident_summary"] == "3 houses flooded"


def test_extract_flags_pii_redacted(monkeypatch):
    client = make_client(monkeypatch)
    chat = "[15/08/2026, 14:32:10] Jane Doe: call +1 868-555-1234 about flooding\n"

    response = client.post(
        "/whatsapp/extract",
        files={"file": ("hour.txt", chat.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 202, response.text
    assert response.json()["pii_redacted"] is True


def test_extract_rejects_empty_file(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/whatsapp/extract",
        files={"file": ("hour.txt", b"", "text/plain")},
    )

    assert response.status_code == 400


def test_extract_rejects_non_txt(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/whatsapp/extract",
        files={"file": ("hour.csv", CHAT.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 400


def test_confirm_writes_submissions_without_calling_llm(monkeypatch):
    class BoomLLM:
        def generate(self, system_prompt: str, user_content: str) -> str:
            raise AssertionError("confirm must not call the LLM")

    monkeypatch.setattr(
        "app.api.whatsapp.get_llm_client",
        lambda purpose="batch": BoomLLM(),
    )
    import app.modules.sitreps.models  # noqa: F401
    import app.modules.survey123.models  # noqa: F401

    Base.metadata.create_all(db_engine)
    client = TestClient(create_app())

    response = client.post(
        "/whatsapp/confirm",
        json={
            "as_at": "2026-08-15T16:00:00",
            "filename": "hour.txt",
            "incidents": [],
            "logs": [
                {
                    "corporation": CORP,
                    "category": "resource",
                    "statement": "200 sandbags remaining at depot",
                    "item": "sandbags",
                    "quantity": 200,
                    "unit": "bags",
                    "status": "available",
                    "source_index": 2,
                    "source_quote": "200 sandbags remaining",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["submissions"]) == 1
    assert body["submissions"][0]["logs_inserted"] == 1
    assert body["submissions"][0]["incidents_inserted"] == 0


def test_confirm_rejects_empty_selection(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post(
        "/whatsapp/confirm",
        json={
            "as_at": "2026-08-15T16:00:00",
            "filename": "hour.txt",
            "incidents": [],
            "logs": [],
        },
    )

    assert response.status_code == 400
    assert "select at least one" in response.json()["detail"].lower()


def _extract(client) -> dict:
    response = client.post(
        "/whatsapp/extract",
        files={"file": ("hour.txt", CHAT.encode("utf-8"), "text/plain")},
        data={"as_at": "2026-08-15T16:00:00"},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_put_draft_updates_rows(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    draft_id = extracted["id"]
    logs = extracted["logs"]
    logs[0]["statement"] = "180 sandbags remaining at depot"
    logs[0]["quantity"] = 180

    response = client.put(
        f"/whatsapp/drafts/{draft_id}",
        json={"incidents": extracted["incidents"], "logs": logs},
    )
    assert response.status_code == 200, response.text
    assert response.json()["logs"][0]["quantity"] == 180


def test_adjust_updates_draft_rows(monkeypatch):
    adjusted = json.dumps(
        {
            "incidents": [
                {
                    "corporation": CORP,
                    "incident_summary": "5 houses flooded",
                    "source_index": 1,
                    "source_quote": "not 3, 5 houses",
                    "included": True,
                }
            ],
            "logs": [],
        }
    )
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON, adjusted])
    extracted = _extract(client)

    response = client.post(
        f"/whatsapp/drafts/{extracted['id']}/adjust",
        json={"instruction": "use the later correction of 5 houses"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["incidents"][0]["incident_summary"] == "5 houses flooded"


def test_adjust_redacts_phones(monkeypatch):
    adjusted = json.dumps(
        {
            "incidents": [],
            "logs": [
                {
                    "corporation": CORP,
                    "category": "resource",
                    "statement": "Call +1 868-555-1234, 200 sandbags remaining",
                    "source_index": 2,
                    "source_quote": "200 sandbags remaining at depot",
                    "included": True,
                }
            ],
        }
    )
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON, adjusted])
    extracted = _extract(client)

    response = client.post(
        f"/whatsapp/drafts/{extracted['id']}/adjust",
        json={"instruction": "keep the depot contact"},
    )
    assert response.status_code == 200, response.text
    statement = response.json()["logs"][0]["statement"]
    assert "[phone]" in statement
    assert "868-555-1234" not in statement


@pytest.mark.workflow("whatsapp_briefing")
def test_briefing_saves_provisional_report_without_sitrep_rows(monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.core.llm import FakeLLMClient
    from app.db import engine as db_engine
    from app.modules.sitreps.models import SitrepIncident

    class ExtractThenNarrate:
        def __init__(self):
            self._used_extract = False
            self._fake = FakeLLMClient()

        def generate(self, system_prompt: str, user_content: str) -> str:
            if not self._used_extract:
                self._used_extract = True
                return EXTRACT_JSON
            return self._fake.generate(system_prompt, user_content)

    client = make_client(monkeypatch, llm_client=ExtractThenNarrate())
    extracted = _extract(client)

    response = client.post(f"/whatsapp/drafts/{extracted['id']}/briefing")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["markdown"].startswith("**Provisional")
    assert body["status"] == "ok"
    assert body["id"]

    Session = sessionmaker(bind=db_engine)
    session = Session()
    assert session.query(SitrepIncident).count() == 0
    session.close()

    draft = client.get(f"/whatsapp/drafts/{extracted['id']}")
    assert draft.status_code == 200, draft.text
    body_draft = draft.json()
    assert body_draft["briefing_report_id"] == body["id"]
    assert body_draft["briefing_stale"] is False


def test_briefing_marks_stale_after_working_set_changes(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.core.llm import FakeLLMClient
    from app.modules.whatsapp import store as wa_store

    class ExtractThenNarrate:
        def __init__(self):
            self._used_extract = False
            self._fake = FakeLLMClient()

        def generate(self, system_prompt: str, user_content: str) -> str:
            if not self._used_extract:
                self._used_extract = True
                return EXTRACT_JSON
            return self._fake.generate(system_prompt, user_content)

    client = make_client(monkeypatch, llm_client=ExtractThenNarrate())
    extracted = _extract(client)

    response = client.post(f"/whatsapp/drafts/{extracted['id']}/briefing")
    assert response.status_code == 202, response.text
    assert client.get(f"/whatsapp/drafts/{extracted['id']}").json()["briefing_stale"] is False

    later = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=5)
    monkeypatch.setattr(wa_store, "_now", lambda: later)
    incidents = extracted["incidents"]
    incidents[0]["incident_summary"] = "4 houses flooded"
    updated = client.put(
        f"/whatsapp/drafts/{extracted['id']}",
        json={"incidents": incidents, "logs": extracted["logs"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["briefing_stale"] is True
    assert updated.json()["briefing_report_id"] == response.json()["id"]


def test_briefing_rejects_empty_included_set(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    incidents = extracted["incidents"]
    logs = extracted["logs"]
    for row in incidents:
        row["included"] = False
    for row in logs:
        row["included"] = False
    client.put(
        f"/whatsapp/drafts/{extracted['id']}",
        json={"incidents": incidents, "logs": logs},
    )

    response = client.post(f"/whatsapp/drafts/{extracted['id']}/briefing")
    assert response.status_code == 400


def test_promote_files_included_rows(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)

    response = client.post(f"/whatsapp/drafts/{extracted['id']}/promote")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["submissions"]) == 1
    assert body["submissions"][0]["incidents_inserted"] == 1
    assert body["submissions"][0]["logs_inserted"] == 1


def test_list_drafts_includes_extracted(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)

    response = client.get("/whatsapp/drafts")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert extracted["id"] in ids


def test_extract_accepts_pasted_text(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/whatsapp/extract",
        data={"text": "Diego Martin: 3 houses flooded in Petit Valley"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["filename"] == "pasted.txt"
    assert body["source_kind"] == "paste"
    assert body["message_count"] == 1
    assert body["incidents"]


def test_extract_pasted_export_text_is_classified_as_export(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/whatsapp/extract", data={"text": CHAT})
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["source_kind"] == "export"
    assert body["filename"] == "pasted.txt"
    assert body["message_count"] == 2


def test_extract_rejects_file_and_text_together(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/whatsapp/extract",
        data={"text": "Diego Martin standing by"},
        files={"file": ("hour.txt", CHAT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 400
    assert "either" in response.json()["detail"].lower()


def test_extract_rejects_neither_file_nor_text(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post("/whatsapp/extract", data={"as_at": "2026-08-15T16:00:00"})
    assert response.status_code == 400


def test_extract_empty_file_with_pasted_text_is_paste(monkeypatch):
    client = make_client(monkeypatch)
    response = client.post(
        "/whatsapp/extract",
        data={"text": "Diego Martin: 3 houses flooded in Petit Valley"},
        files={"file": ("", b"", "application/octet-stream")},
    )
    assert response.status_code == 202, response.text
    assert response.json()["source_kind"] == "paste"
    assert response.json()["filename"] == "pasted.txt"


def test_extract_returns_row_ids_and_empty_thread(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    assert extracted["incidents"][0]["row_id"]
    assert extracted["logs"][0]["row_id"]
    assert extracted["messages"] == []
    assert extracted["manual_fields"] == []
    assert isinstance(extracted["missing"], list)


def test_put_draft_records_manual_fields(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    incidents = extracted["incidents"]
    incidents[0]["corporation"] = CORP
    response = client.put(
        f"/whatsapp/drafts/{extracted['id']}",
        json={
            "incidents": incidents,
            "logs": extracted["logs"],
            "manual_fields": [f"incident:{incidents[0]['row_id']}.corporation"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["manual_fields"] == [
        f"incident:{incidents[0]['row_id']}.corporation"
    ]


def _turn_response(summary: str = "5 houses flooded") -> str:
    return json.dumps(
        {
            "assistant_message": f"Updated: {summary}.",
            "working": {
                "as_at": "2026-08-15T16:00:00",
                "incidents": [
                    {
                        "row_id": "1",
                        "corporation": CORP,
                        "incident_summary": summary,
                        "source_index": 1,
                        "source_quote": "not 3, 5 houses",
                        "included": True,
                    }
                ],
                "logs": [],
            },
        }
    )


def test_turn_updates_draft_and_appends_messages(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON, _turn_response()])
    extracted = _extract(client)

    response = client.post(
        f"/whatsapp/drafts/{extracted['id']}/turns",
        json={"message": "use the later correction of 5 houses"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incidents"][0]["incident_summary"] == "5 houses flooded"
    assert [item["role"] for item in body["messages"]] == ["user", "assistant"]
    assert "5 houses" in body["messages"][-1]["content"]


def test_turn_rejects_empty_message(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    response = client.post(
        f"/whatsapp/drafts/{extracted['id']}/turns",
        json={"message": "  "},
    )
    assert response.status_code == 400
    assert "message" in response.json()["detail"].lower()


def test_turn_rejects_draft_that_is_not_ready(monkeypatch):
    client = make_client(monkeypatch)
    extracted = _extract(client)
    from sqlalchemy.orm import sessionmaker

    from app.db import engine as db_engine
    from app.modules.whatsapp.store import get_draft, mark_draft_running

    Session = sessionmaker(bind=db_engine)
    session = Session()
    draft = get_draft(session, extracted["id"])
    assert draft is not None
    mark_draft_running(draft, session)
    session.close()

    response = client.post(
        f"/whatsapp/drafts/{extracted['id']}/turns",
        json={"message": "Diego Martin not Siparia"},
    )
    assert response.status_code == 400


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_stream_turn_emits_text_then_whatsapp_updated(monkeypatch):
    client = make_client(monkeypatch, llm_responses=[EXTRACT_JSON, _turn_response()])
    extracted = _extract(client)
    draft_id = extracted["id"]

    with client.stream(
        "POST",
        f"/whatsapp/drafts/{draft_id}/turns/stream",
        json={
            "messages": [
                {"role": "user", "content": "use the later correction of 5 houses"}
            ],
            "data": {"draft_id": draft_id},
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
    assert custom["name"] == "whatsapp.updated"
    snapshot = custom["value"]
    assert snapshot["incidents"][0]["incident_summary"] == "5 houses flooded"
    assert snapshot["messages"]
