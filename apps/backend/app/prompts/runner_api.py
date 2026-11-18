"""Eval runner: run the prompt test set in prod, against the real NIM, from
a laptop.

A separate small app (docker-compose.evals.yml), built from the backend
image so it always has the last pushed prompts and test set. It sits on the
network next to nim-prod and is reached over HTTPS on its own domain. Every
route except /health needs EVAL_RUNNER_API_KEY as a Bearer token; with no key
configured it refuses everything.

  POST /evals            start a test-set run {prompt_id, version, draft_text,
                         repeat, cases, inline_cases}
  GET  /evals            recent runs (test-set runs and replays)
  GET  /evals/{id}       progress, then the full result
  GET  /evals/compare    ?a=<id>&b=<id>
  GET  /sources          which databases chats can be replayed from
  GET  /sessions         ?source=&corp=&since=&status=  capture chats, dated
  GET  /sessions/{id}    ?source=  one chat's turns
  POST /replays          replay a chat {source, session_id, versions,
                         draft_text, mode, turns}
  GET  /info             deployed prompt versions and model
  /v1/...                OpenAI-style passthrough to NIM, for one-off checks

One run at a time: it shares the production GPU with live traffic. Replays
read the databases read-only (app/prompts/replay.py)."""

import hmac
import json
import logging
import threading
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.config import settings
from app.core.llm import get_llm_client, model_label
from app.prompts import replay
from app.prompts.evals import (
    cases_from_items,
    compare_lines,
    load_cases,
    run_eval,
    summary_lines,
)
from app.prompts.registry import (
    Prompt,
    draft_prompt,
    load_spec,
    load_version,
    prompt_ids,
)

logger = logging.getLogger("eval_runner")

MAX_PROXY_BODY = 1_000_000
PROXY_TIMEOUT = httpx.Timeout(300.0, connect=10.0)
_KEPT_RUNS = 200

app = FastAPI(title="DMCU eval runner", docs_url=None, redoc_url=None, openapi_url=None)


def require_key(request: Request) -> None:
    expected = settings.eval_runner_api_key
    if not expected:
        raise HTTPException(status_code=503, detail="EVAL_RUNNER_API_KEY is not set")
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or wrong API key")


# --- runs -----------------------------------------------------------------------


MAX_DRAFT_CHARS = 100_000


class EvalRequest(BaseModel):
    prompt_id: str = "corp_capture"
    version: int | None = None
    # Uncommitted prompt text to try instead of a version.
    draft_text: str | None = Field(default=None, max_length=MAX_DRAFT_CHARS)
    repeat: int = Field(default=3, ge=1, le=5)
    cases: list[str] | None = None
    # Cases in the cases.yaml form, run instead of the test set.
    inline_cases: list[dict] | None = Field(default=None, max_length=50)


class ReplayRequest(BaseModel):
    source: str
    session_id: int
    prompt_id: str = "corp_capture"
    # Versions to replay with; empty means the current one.
    versions: list[int] = Field(default_factory=list, max_length=4)
    draft_text: str | None = Field(default=None, max_length=MAX_DRAFT_CHARS)
    mode: str = "recorded"
    # Only these turn seqs (from GET /sessions/{id}); default all.
    turns: list[int] | None = None


_lock = threading.Lock()
_runs: dict[str, dict] = {}


def _results_dir() -> Path:
    path = Path(settings.eval_results_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _result_file(run_id: str) -> Path:
    if not run_id.replace("-", "").replace("_", "").replace("@", "").isalnum():
        raise HTTPException(status_code=400, detail="bad run id")
    return _results_dir() / f"{run_id}.json"


def _running() -> dict | None:
    return next((run for run in _runs.values() if run["status"] == "running"), None)


def _start(run_id: str, meta: dict, total: int, work) -> None:
    """Register a run and do `work(progress)` in a thread; its result is saved
    as {run_id}.json. One run at a time across evals and replays."""
    with _lock:
        busy = _running()
        if busy is not None:
            raise HTTPException(status_code=409, detail=f"run {busy['id']} is still going")
        _runs[run_id] = {
            "id": run_id,
            "status": "running",
            **meta,
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "total": total,
            "done": 0,
            "log": [],
        }
        for old in list(_runs)[:-_KEPT_RUNS]:
            _runs.pop(old, None)
    state = _runs[run_id]

    def progress(line: str) -> None:
        state["done"] += 1
        state["log"].append(line)

    def target() -> None:
        try:
            result = work(progress)
            result["id"] = run_id
            _result_file(run_id).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            state.update(status="done", summary=result["summary"])
            logger.info("run %s done", run_id)
        except Exception as exc:
            state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            logger.exception("run %s failed", run_id)

    threading.Thread(target=target, daemon=True).start()


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S")


def _version_tag(prompt: Prompt) -> str:
    return prompt.ref.split("@", 1)[1] if prompt.version == 0 else f"v{prompt.version}"


def _prompt(prompt_id: str, version: int | None, draft_text: str | None = None) -> Prompt:
    if prompt_id not in prompt_ids():
        raise HTTPException(status_code=404, detail=f"unknown prompt {prompt_id}")
    if draft_text is not None:
        if not draft_text.strip():
            raise HTTPException(status_code=400, detail="draft_text is empty")
        return draft_prompt(prompt_id, draft_text)
    try:
        return load_version(prompt_id, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/info", dependencies=[Depends(require_key)])
def info() -> dict:
    prompts = []
    for prompt_id in prompt_ids():
        current = load_version(prompt_id)
        prompts.append(
            {
                "id": prompt_id,
                "version": current.version,
                "hash": current.hash,
                "description": load_spec(prompt_id).description,
            }
        )
    return {"prompts": prompts, "model": model_label(get_llm_client("chat"))}


@app.post("/evals", status_code=202, dependencies=[Depends(require_key)])
def start_eval(request: EvalRequest) -> dict:
    prompt = _prompt(request.prompt_id, request.version, request.draft_text)
    if request.inline_cases:
        try:
            cases = cases_from_items(request.inline_cases)
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=f"bad inline case: {exc}") from exc
    else:
        cases = load_cases(request.prompt_id)
        if request.cases:
            unknown = set(request.cases) - {case.id for case in cases}
            if unknown:
                raise HTTPException(status_code=400, detail=f"unknown cases: {sorted(unknown)}")
            cases = [case for case in cases if case.id in set(request.cases)]
    run_id = f"{_stamp()}-{prompt.id}@{_version_tag(prompt)}"
    total = len(cases) * request.repeat
    _start(
        run_id,
        {"kind": "eval", "prompt": prompt.ref, "prompt_hash": prompt.hash},
        total,
        lambda progress: run_eval(prompt, get_llm_client("chat"), cases, request.repeat, progress),
    )
    logger.info("eval %s started: %d cases x%d", run_id, len(cases), request.repeat)
    return {"id": run_id, "prompt": prompt.ref, "prompt_hash": prompt.hash, "total": total}


@app.get("/evals", dependencies=[Depends(require_key)])
def list_evals() -> list[dict]:
    rows = {run_id: {k: v for k, v in run.items() if k != "log"} for run_id, run in _runs.items()}
    for path in sorted(_results_dir().glob("*.json")):
        if path.stem in rows:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("kind") == "replay":
            rows[path.stem] = {
                "id": path.stem,
                "kind": "replay",
                "status": "done",
                "prompt": ", ".join(item["ref"] for item in data["prompts"]),
                "model": data["model"],
                "started_at": data["run_at"],
                "session": f"{data.get('source')}/{data.get('session_id')}",
            }
            continue
        rows[path.stem] = {
            "id": path.stem,
            "kind": "eval",
            "status": "done",
            "prompt": data["prompt"],
            "model": data["model"],
            "started_at": data["run_at"],
            "pass_rate": data["summary"]["pass_rate"],
        }
    return sorted(rows.values(), key=lambda row: row["id"], reverse=True)


def _load_result(run_id: str) -> dict:
    path = _result_file(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"no finished run {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/evals/compare", dependencies=[Depends(require_key)])
def compare_evals(a: str, b: str) -> dict:
    return {"lines": compare_lines(_load_result(a), _load_result(b))}


@app.get("/evals/{run_id}", dependencies=[Depends(require_key)])
def get_eval(run_id: str) -> dict:
    state = _runs.get(run_id)
    if state is not None and state["status"] != "done":
        return state
    result = _load_result(run_id)
    lines = replay.replay_lines(result) if result.get("kind") == "replay" else summary_lines(result)
    return {"status": "done", "summary_lines": lines, "result": result}


# --- recorded chats ---------------------------------------------------------------


def _source(source: str):
    try:
        return replay.open_source(source)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"unknown source {source!r}; configured: {sorted(replay.source_urls())}",
        ) from exc


@app.get("/sources", dependencies=[Depends(require_key)])
def sources() -> dict:
    return {"sources": sorted(replay.source_urls())}


@app.get("/sessions", dependencies=[Depends(require_key)])
def sessions(
    source: str,
    corp: str | None = None,
    since: date | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    with _source(source) as db:
        return replay.list_sessions(db, corp, since, status, max(1, min(limit, 200)))


@app.get("/sessions/{session_id}", dependencies=[Depends(require_key)])
def session(session_id: int, source: str) -> dict:
    with _source(source) as db:
        detail = replay.session_detail(db, session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"no session {session_id} in {source}")
    return detail


@app.post("/replays", status_code=202, dependencies=[Depends(require_key)])
def start_replay(request: ReplayRequest) -> dict:
    if request.mode not in replay.MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {replay.MODES}")
    prompts = [_prompt(request.prompt_id, version) for version in request.versions]
    if request.draft_text is not None:
        prompts.append(_prompt(request.prompt_id, None, request.draft_text))
    if not prompts:
        prompts = [_prompt(request.prompt_id, None)]
    with _source(request.source) as db:
        try:
            turns = replay.recorded_turns(db, request.session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"no session {request.session_id} in {request.source}"
            ) from exc
        corporation = db.get(replay.CaptureSession, request.session_id).corporation
    if request.turns:
        if request.mode == "chained":
            raise HTTPException(status_code=400, detail="chained mode replays the whole chat; drop turns")
        wanted = set(request.turns)
        turns = [turn for turn in turns if turn.seq in wanted]
    if not turns:
        raise HTTPException(status_code=400, detail="no officer turns to replay")
    total = len(turns) * len(prompts)
    if total > replay.MAX_MODEL_CALLS:
        raise HTTPException(
            status_code=400,
            detail=f"{total} model calls; at most {replay.MAX_MODEL_CALLS}. Pick turns or fewer versions.",
        )
    run_id = f"{_stamp()}-replay-{request.source}-{request.session_id}"
    meta = {"source": request.source, "session_id": request.session_id, "corporation": corporation}

    def work(progress) -> dict:
        result = replay.replay_session(turns, prompts, get_llm_client("chat"), request.mode, progress)
        return {**result, **meta}

    _start(run_id, {"kind": "replay", "prompt": ", ".join(p.ref for p in prompts), **meta}, total, work)
    logger.info("replay %s started: %d turns x%d prompts", run_id, len(turns), len(prompts))
    return {"id": run_id, "prompts": [p.ref for p in prompts], "turns": len(turns), "total": total}


# --- NIM passthrough ------------------------------------------------------------

_HOP_HEADERS = {
    "authorization", "host", "content-length", "connection", "keep-alive",
    "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization",
}


def nim_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.nim_base_url.rstrip("/"), timeout=PROXY_TIMEOUT)


@app.api_route(
    "/v1/{path:path}", methods=["GET", "POST"], dependencies=[Depends(require_key)]
)
async def nim_passthrough(path: str, request: Request) -> StreamingResponse:
    body = await request.body()
    if len(body) > MAX_PROXY_BODY:
        raise HTTPException(status_code=413, detail="request too large")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_HEADERS}
    client = nim_client()
    upstream = await client.send(
        client.build_request(
            request.method, f"/v1/{path}", params=request.query_params, headers=headers, content=body
        ),
        stream=True,
    )
    logger.info("nim %s /v1/%s -> %s (%d bytes in)", request.method, path, upstream.status_code, len(body))

    async def close() -> None:
        await upstream.aclose()
        await client.aclose()

    return StreamingResponse(
        # Decoded bytes, so the content-encoding header is dropped with them.
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        headers={
            k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_HEADERS | {"content-encoding"}
        },
        background=BackgroundTask(close),
    )
