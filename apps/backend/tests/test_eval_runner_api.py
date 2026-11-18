import json
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.llm import FakeLLMClient
from app.prompts import runner_api

KEY = "test-key-123"
AUTH = {"Authorization": f"Bearer {KEY}"}
ONE_CASE = {"repeat": 1, "cases": ["couva-assessments-ongoing"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_api.settings, "eval_runner_api_key", KEY)
    monkeypatch.setattr(runner_api.settings, "eval_results_dir", str(tmp_path))
    monkeypatch.setattr(runner_api, "_runs", {})
    monkeypatch.setattr(runner_api, "get_llm_client", lambda purpose="batch": FakeLLMClient())
    return TestClient(runner_api.app)


def _wait(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/evals/{run_id}", headers=AUTH).json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_every_route_but_health_needs_the_key(client):
    assert client.get("/health").status_code == 200
    for method, path in [("get", "/info"), ("get", "/evals"), ("post", "/evals"), ("get", "/v1/models")]:
        assert getattr(client, method)(path).status_code == 401
        assert getattr(client, method)(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_without_a_configured_key_it_refuses_everything(client, monkeypatch):
    monkeypatch.setattr(runner_api.settings, "eval_runner_api_key", "")

    assert client.get("/info", headers={"Authorization": "Bearer "}).status_code == 503


def test_a_run_reports_progress_then_its_result(client):
    started = client.post("/evals", json=ONE_CASE, headers=AUTH)

    assert started.status_code == 202, started.text
    run_id = started.json()["id"]
    assert "corp_capture@v" in run_id
    body = _wait(client, run_id)
    assert body["status"] == "done"
    assert body["result"]["prompt_hash"] == started.json()["prompt_hash"]
    assert body["result"]["cases"][0]["id"] == "couva-assessments-ongoing"
    assert any("checks passed" in line for line in body["summary_lines"])
    listed = client.get("/evals", headers=AUTH).json()
    assert listed[0]["id"] == run_id


def test_a_finished_run_survives_a_restart(client, monkeypatch):
    run_id = client.post("/evals", json=ONE_CASE, headers=AUTH).json()["id"]
    _wait(client, run_id)
    monkeypatch.setattr(runner_api, "_runs", {})

    assert client.get(f"/evals/{run_id}", headers=AUTH).json()["status"] == "done"
    assert [row["id"] for row in client.get("/evals", headers=AUTH).json()] == [run_id]


def test_one_run_at_a_time(client, monkeypatch):
    release = threading.Event()

    class SlowLLM(FakeLLMClient):
        def generate(self, system_prompt, user_content):
            release.wait(5)
            return super().generate(system_prompt, user_content)

    monkeypatch.setattr(runner_api, "get_llm_client", lambda purpose="batch": SlowLLM())
    first = client.post("/evals", json=ONE_CASE, headers=AUTH).json()["id"]

    second = client.post("/evals", json=ONE_CASE, headers=AUTH)

    assert second.status_code == 409
    release.set()
    _wait(client, first)


def test_an_earlier_frozen_version_can_be_run(client):
    started = client.post("/evals", json={**ONE_CASE, "version": 1}, headers=AUTH)

    assert started.status_code == 202
    assert started.json()["prompt"] == "corp_capture@1"
    _wait(client, started.json()["id"])


def test_unknown_versions_cases_and_run_ids_are_rejected(client):
    assert client.post("/evals", json={"version": 999}, headers=AUTH).status_code == 404
    assert client.post("/evals", json={"cases": ["nope"]}, headers=AUTH).status_code == 400
    assert client.get("/evals/..%2Fetc", headers=AUTH).status_code in (400, 404)


def test_compare_two_runs(client):
    a = client.post("/evals", json={**ONE_CASE, "version": 1}, headers=AUTH).json()["id"]
    _wait(client, a)
    b = client.post("/evals", json=ONE_CASE, headers=AUTH).json()["id"]
    _wait(client, b)

    lines = client.get("/evals/compare", params={"a": a, "b": b}, headers=AUTH).json()["lines"]

    assert lines[0].startswith("corp_capture@1")


def test_v1_requests_pass_through_to_nim_without_the_runner_key(client, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    monkeypatch.setattr(
        runner_api,
        "nim_client",
        lambda: httpx.AsyncClient(base_url="http://nim", transport=httpx.MockTransport(handler)),
    )

    response = client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hi"
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] is None  # the personal key never reaches NIM
    assert seen["body"]["model"] == "openai/gpt-oss-20b"


def test_oversized_passthrough_is_refused(client):
    response = client.post("/v1/chat/completions", content=b"x" * (runner_api.MAX_PROXY_BODY + 1), headers=AUTH)

    assert response.status_code == 413
