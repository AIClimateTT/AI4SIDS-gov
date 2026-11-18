"""Eval runner: run the prompt test set in prod, against the real NIM, from
a laptop.

A separate small app (docker-compose.evals.yml), built from the backend
image so it always has the last pushed prompts and test set. It sits on the
network next to nim-prod and is reached over HTTPS on its own domain. Every
route except /health needs EVAL_RUNNER_API_KEY as a Bearer token; with no key
configured it refuses everything.

  POST /evals            start a run {prompt_id, version, repeat, cases}
  GET  /evals            recent runs
  GET  /evals/{id}       progress, then the full result
  GET  /evals/compare    ?a=<id>&b=<id>
  GET  /info             deployed prompt versions and model
  /v1/...                OpenAI-style passthrough to NIM, for one-off checks

One run at a time: it shares the production GPU with live traffic."""

import hmac
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.config import settings
from app.core.llm import get_llm_client, model_label
from app.prompts.evals import compare_lines, load_cases, run_eval, summary_lines
from app.prompts.registry import load_spec, load_version, prompt_ids

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


class EvalRequest(BaseModel):
    prompt_id: str = "corp_capture"
    version: int | None = None
    repeat: int = Field(default=3, ge=1, le=5)
    cases: list[str] | None = None


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


def _execute(run_id: str, request: EvalRequest, prompt, cases) -> None:
    state = _runs[run_id]

    def progress(line: str) -> None:
        state["done"] += 1
        state["log"].append(line)

    try:
        result = run_eval(prompt, get_llm_client("chat"), cases, request.repeat, progress)
        result["id"] = run_id
        _result_file(run_id).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        state.update(status="done", summary=result["summary"])
        logger.info("eval %s done: %s", run_id, result["summary"]["pass_rate"])
    except Exception as exc:
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        logger.exception("eval %s failed", run_id)


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
    if request.prompt_id not in prompt_ids():
        raise HTTPException(status_code=404, detail=f"unknown prompt {request.prompt_id}")
    try:
        prompt = load_version(request.prompt_id, request.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    cases = load_cases(request.prompt_id)
    if request.cases:
        unknown = set(request.cases) - {case.id for case in cases}
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case.id in set(request.cases)]
    with _lock:
        busy = _running()
        if busy is not None:
            raise HTTPException(status_code=409, detail=f"run {busy['id']} is still going")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        run_id = f"{stamp}-{prompt.id}@v{prompt.version}"
        _runs[run_id] = {
            "id": run_id,
            "status": "running",
            "prompt": prompt.ref,
            "prompt_hash": prompt.hash,
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "total": len(cases) * request.repeat,
            "done": 0,
            "log": [],
        }
        for old in list(_runs)[:-_KEPT_RUNS]:
            _runs.pop(old, None)
    threading.Thread(target=_execute, args=(run_id, request, prompt, cases), daemon=True).start()
    logger.info("eval %s started: %d cases x%d", run_id, len(cases), request.repeat)
    return {"id": run_id, "prompt": prompt.ref, "prompt_hash": prompt.hash, "total": len(cases) * request.repeat}


@app.get("/evals", dependencies=[Depends(require_key)])
def list_evals() -> list[dict]:
    rows = {run_id: {k: v for k, v in run.items() if k != "log"} for run_id, run in _runs.items()}
    for path in sorted(_results_dir().glob("*.json")):
        if path.stem in rows:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows[path.stem] = {
            "id": path.stem,
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
    return {"status": "done", "summary_lines": summary_lines(result), "result": result}


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
