"""Replaying recorded capture chats on the eval runner (app/prompts/replay.py)."""

import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.llm import FakeLLMClient
from app.db import Base
from app.modules.capture.models import CaptureSession
from app.modules.capture.store import (
    apply_working_set,
    create_session,
    record_turn,
    save_session,
    working_set_from_session,
)
from app.modules.capture.turn import run_turn
from app.prompts import replay, runner_api
from app.prompts.registry import load_version

KEY = "test-key-123"
AUTH = {"Authorization": f"Bearer {KEY}"}
CORP = "arima_borough_corporation"
FIRST = "Flooding along Tumpuna Road, 9 homes, since 3am."
SECOND = "Now 14 homes on Tumpuna Road."


def _reply(households: int) -> str:
    return json.dumps(
        {
            "assistant_message": f"Recorded {households} homes.",
            "capture": {
                "incidents": [
                    {"row_id": "1", "incident_scope": "area", "community": "Arima",
                     "street": "Tumpuna Road", "incident_type": "flooding",
                     "incident_summary": "Flooding.", "households_affected": households}
                ]
            },
        }
    )


def _officer_turn(db: Session, row: CaptureSession, message: str, households: int) -> None:
    prompt = load_version("corp_capture")
    done = run_turn(
        working_set_from_session(row),
        row.messages, message, FakeLLMClient(responses=[_reply(households)]), system_prompt=prompt.text,
    )
    apply_working_set(row, done.working)
    row.messages = [m.model_dump(mode="json") for m in done.messages]
    record_turn(db, row, "turn", user_message=message, assistant_message=done.assistant_message,
                parse_ok=True, prompt=prompt, model="nim:test")
    save_session(db, row)


@pytest.fixture
def source(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'source.db'}"
    writer = create_engine(url)
    Base.metadata.create_all(writer)
    with Session(writer) as db:
        row = create_session(db, corporation=CORP)
        _officer_turn(db, row, FIRST, 9)
        record_turn(db, row, "edit")  # a manual edit between turns
        _officer_turn(db, row, SECOND, 14)
        session_id = row.id
    monkeypatch.setattr(replay.settings, "eval_staging_database_url", url)
    monkeypatch.setattr(replay.settings, "eval_prod_database_url", "")
    replay._engine.cache_clear()
    yield session_id
    replay._engine.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_api.settings, "eval_runner_api_key", KEY)
    monkeypatch.setattr(runner_api.settings, "eval_results_dir", str(tmp_path / "results"))
    monkeypatch.setattr(runner_api, "_runs", {})
    monkeypatch.setattr(runner_api, "get_llm_client", lambda purpose="batch": FakeLLMClient(responses=[_reply(14)]))
    return TestClient(runner_api.app)


def _wait(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/evals/{run_id}", headers=AUTH).json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("run did not finish")


# --- reading recorded chats -----------------------------------------------------


def test_recorded_turns_start_from_what_the_officer_saw(source):
    with replay.open_source("staging") as db:
        turns = replay.recorded_turns(db, source)

    assert [turn.message for turn in turns] == [FIRST, SECOND]
    first, second = turns
    assert first.before == {} and first.history[-1]["role"] == "assistant"
    assert [m["content"] for m in second.history if m["role"] == "user"] == [FIRST]
    # The second turn starts from the snapshot after the edit, not the first turn.
    assert second.before["incidents"][0]["households_affected"] == 9
    assert second.after["incidents"][0]["households_affected"] == 14
    assert second.prompt == load_version("corp_capture").ref


def test_sources_are_opened_read_only(source):
    with replay.open_source("staging") as db, pytest.raises(OperationalError):
        db.get(CaptureSession, source).status = "filed"
        db.commit()


def test_listing_filters_by_corporation_and_dates_each_chat(source):
    with replay.open_source("staging") as db:
        rows = replay.list_sessions(db, corporation="arima")
        none = replay.list_sessions(db, corporation="siparia")

    assert none == []
    assert rows[0]["id"] == source
    assert rows[0]["officer_turns"] == 2
    assert rows[0]["prompts"] == [load_version("corp_capture").ref]
    assert rows[0]["first_message"] == FIRST
    assert rows[0]["updated_at"][:4].isdigit()


# --- replaying -------------------------------------------------------------------


def test_recorded_mode_shows_where_a_version_differs(source):
    with replay.open_source("staging") as db:
        turns = replay.recorded_turns(db, source)
    prompt = load_version("corp_capture")

    result = replay.replay_session(turns, [prompt], FakeLLMClient(responses=[_reply(12)]))

    first, second = (turn["replays"][prompt.ref] for turn in result["turns"])
    assert any("12" in change for change in first["vs_recorded"])
    assert second["vs_recorded"] == ["incident 1.households_affected: 14 → 12"]
    assert result["summary"][prompt.ref]["differ_from_recorded"] == 2
    assert any("turn" in line for line in replay.replay_lines({**result, "source": "staging", "session_id": source}))


def test_two_versions_are_also_compared_to_each_other(source):
    with replay.open_source("staging") as db:
        turns = replay.recorded_turns(db, source)
    v1, current = load_version("corp_capture", 1), load_version("corp_capture")

    result = replay.replay_session(turns, [v1, current], FakeLLMClient(responses=[_reply(14)]))

    assert result["turns"][1]["replays"][current.ref][f"vs_{v1.ref}"] == []


def test_chained_mode_carries_the_replays_own_result_forward(source):
    with replay.open_source("staging") as db:
        turns = replay.recorded_turns(db, source)
    seen: list[dict] = []

    class Recording(FakeLLMClient):
        def generate(self, system_prompt, user_content):
            seen.append(json.loads(user_content))
            return _reply(11)

    replay.replay_session(turns, [load_version("corp_capture")], Recording(), mode="chained")

    assert seen[1]["capture"]["incidents"][0]["households_affected"] == 11


# --- runner endpoints ------------------------------------------------------------


def test_sessions_and_replay_over_http(client, source):
    assert client.get("/sources", headers=AUTH).json() == {"sources": ["staging"]}
    listed = client.get("/sessions", params={"source": "staging", "corp": "arima"}, headers=AUTH).json()
    assert listed[0]["id"] == source
    detail = client.get(f"/sessions/{source}", params={"source": "staging"}, headers=AUTH).json()
    assert [turn["kind"] for turn in detail["turns"]] == ["turn", "edit", "turn"]

    started = client.post(
        "/replays", json={"source": "staging", "session_id": source, "versions": [1, 2]}, headers=AUTH
    )

    assert started.status_code == 202, started.text
    assert started.json()["total"] == 4
    body = _wait(client, started.json()["id"])
    assert body["status"] == "done"
    assert body["result"]["corporation"] == CORP
    assert body["summary_lines"][0].startswith(f"replay of staging session {source}")
    runs = client.get("/evals", headers=AUTH).json()
    assert runs[0]["kind"] == "replay"


def test_replay_rejects_unknown_sources_sessions_and_oversized_runs(client, source, monkeypatch):
    assert client.get("/sessions", params={"source": "prod"}, headers=AUTH).status_code == 404
    bad = client.post("/replays", json={"source": "staging", "session_id": 999}, headers=AUTH)
    assert bad.status_code == 404
    chained_subset = client.post(
        "/replays", json={"source": "staging", "session_id": source, "mode": "chained", "turns": [1]}, headers=AUTH
    )
    assert chained_subset.status_code == 400
    monkeypatch.setattr(replay, "MAX_MODEL_CALLS", 1)
    too_big = client.post("/replays", json={"source": "staging", "session_id": source}, headers=AUTH)
    assert too_big.status_code == 400


def test_replay_routes_need_the_key(client, source):
    assert client.get("/sessions", params={"source": "staging"}).status_code == 401
    assert client.post("/replays", json={"source": "staging", "session_id": source}).status_code == 401


def test_inline_cases_and_a_draft_prompt(client):
    case = {
        "id": "try-once",
        "message": "Flooding along Tumpuna Road, 14 homes.",
        "today": "2026-11-18",
        "checks": [{"kind": "row", "rows": "incidents", "where": {"street": "Tumpuna"},
                    "expect": {"households_affected": 14}}],
    }

    started = client.post(
        "/evals", json={"repeat": 1, "inline_cases": [case], "draft_text": "Draft prompt."}, headers=AUTH
    )

    assert started.status_code == 202, started.text
    assert started.json()["prompt"].startswith("corp_capture@draft-")
    body = _wait(client, started.json()["id"])
    assert body["result"]["cases"][0]["id"] == "try-once"
    assert body["result"]["summary"]["pass_rate"] == 1.0
    assert client.post("/evals", json={"inline_cases": [{"id": "x"}]}, headers=AUTH).status_code == 400
