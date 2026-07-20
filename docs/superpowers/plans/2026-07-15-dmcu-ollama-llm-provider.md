# DMCU Reporting — Replace Anthropic LLM Client with Ollama Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `AnthropicLLMClient` (built in Step 5, never actually usable since no Anthropic API key is intended for this project) with `OllamaLLMClient`, wrapping a local/self-hosted Ollama server via `langchain-ollama`. Local development and testing use `gemma3:4b` (already pulled on this machine); deployment will point the same client at a `gpt-oss:20b` model — both are just a config value, no code difference between the two.

**Architecture:** This is a scoped substitution inside Step 5's already-shipped `app/core/llm.py` and `app/config.py`, not a new pipeline step — `generate_report`, the retry logic, the citation checker, and every other Step 1–5 component are untouched, because they only ever depend on the provider-agnostic `LLMClient` Protocol (`generate(system_prompt, user_content) -> str`). Everything below was verified by actually running it against the real local Ollama server during planning (not guessed) — see the verification note in Global Constraints.

**Tech Stack:** Removes `anthropic`; adds `langchain-ollama` (confirmed installable, version 1.1.0 as of planning, pulling in `langchain-core`/`langsmith` transitively).

## Global Constraints

- **This entire integration was tested live against the real local Ollama server during planning**, not assumed: `ollama --version` confirmed 0.30.7 running with `gemma3:4b`/`gemma3:12b` pulled (no `llama3.2` — the user confirmed using `gemma3:4b` for local testing instead); `langchain_ollama.ChatOllama(base_url=..., model="gemma3:4b").invoke([("system", ...), ("human", ...)])` was called live and returned a real `AIMessage` with a plain-string `.content` field in ~5 seconds; `ChatOllama(...)` construction alone (pointed at an unreachable address, RFC 5737 `192.0.2.1`) was independently confirmed to make **zero network calls** — it returned in 5ms — so constructing an `OllamaLLMClient` without calling `.generate()` is safe in tests, consistent with `PLAN.md` §7's "no LLM call anywhere except `core/llm.py`; everything else must be testable without a network."
- **Confirmed decisions from the project owner:** remove `AnthropicLLMClient` entirely (dead code — no Anthropic key is intended for this project, and Step 4's YAGNI guardrails apply); use LangChain (`langchain-ollama`'s `ChatOllama`) rather than a bare Ollama HTTP client, since the owner may use LangChain elsewhere; local/test model is `gemma3:4b` (already on disk), deployment model will be `gpt-oss:20b` (an Ollama-hosted OpenAI open-weight model) — both are pure config, no code branches on which one is active.
- `Settings` gains `llm_provider: Literal["fake", "ollama"] = "ollama"` (defaults to the real local Ollama path, matching the owner's stated intent to actually use it for testing now — not gated behind an opt-in flag the way Anthropic's API-key presence used to gate it), `ollama_base_url: str = "http://localhost:11434"`, `ollama_model: str = "gemma3:4b"`. The `anthropic_api_key`/`anthropic_model` fields are removed, not deprecated — nothing else in the codebase reads them (confirmed via `grep -rln "anthropic" apps/backend` during planning: only `pyproject.toml`, `app/config.py`, `app/core/llm.py`, `tests/test_llm.py`, `tests/test_config.py` reference it anywhere — no leakage into `main.py`, `cli.py`, or `engine.py`, which only ever depend on the `LLMClient` Protocol).
- `OllamaLLMClient` accepts an optional `chat` parameter (`chat: "ChatOllama | None" = None`) for dependency injection, mirroring the exact pattern `AnthropicLLMClient` used — tests inject a `MagicMock`, never touch the real network. `get_default_llm_client()`'s own test that exercises the real (non-mocked) construction path only asserts `isinstance(...)`, never calls `.generate()` — safe per the verified-zero-network-calls-at-construction fact above.
- `FakeLLMClient` (Step 5 Task 3) is completely unchanged — every existing test that constructs it directly (`test_llm.py`'s 3 fake-client tests, and every engine/renderer/CLI test across Steps 5) is untouched by this plan.
- This plan preserves the exact automated-suite test count for the two modified test files (`test_config.py` stays at 2 tests, `test_llm.py` stays at 6 tests) — only the fields/assertions inside them change, since this is a 1:1 provider substitution, not new functionality. The overall suite count therefore stays at 181.
- Definition of done: `cd apps/backend && uv run pytest -v` — all 181 tests pass, 0 failures, no test makes a real network call; a manual, non-automated verification (Task 1 Step 8) runs `cli.py generate` against the real local Ollama server and confirms a complete, correctly-cited markdown report comes back from a real `gemma3:4b` completion (not the fake auto-narrative path).

---

### Task 1: Replace `AnthropicLLMClient` with `OllamaLLMClient`

**Files:**
- Modify: `apps/backend/pyproject.toml` (remove `anthropic`, add `langchain-ollama`)
- Modify: `apps/backend/app/config.py`
- Modify: `apps/backend/app/core/llm.py`
- Modify: `apps/backend/tests/test_config.py`
- Modify: `apps/backend/tests/test_llm.py`

**Interfaces:**
- Consumes: nothing new beyond `langchain_ollama.ChatOllama`.
- Produces: `Settings.llm_provider: Literal["fake", "ollama"]`, `Settings.ollama_base_url: str`, `Settings.ollama_model: str` (replacing `anthropic_api_key`/`anthropic_model`); `app.core.llm.OllamaLLMClient(base_url: str, model: str, chat: "ChatOllama | None" = None)` implementing the unchanged `LLMClient` Protocol (replacing `AnthropicLLMClient`); `get_default_llm_client()` now branches on `settings.llm_provider` instead of `settings.anthropic_api_key`. Nothing outside `app/config.py`/`app/core/llm.py` changes — `engine.py`, `main.py`, `cli.py`, and every template/metric/ingest module are untouched, since they only ever depend on the `LLMClient` Protocol and `get_default_llm_client()`, never on a specific provider class.

- [ ] **Step 1: Swap the dependency**

```bash
cd apps/backend
uv remove anthropic
UV_HTTP_TIMEOUT=120 uv add langchain-ollama
```

Expected: both exit 0; `pyproject.toml`'s `dependencies` list no longer has `anthropic`, now has `langchain-ollama`. Use the extended `UV_HTTP_TIMEOUT` — a transitive dependency (`langsmith`) hit a 30s timeout during planning on this network; 120s resolved it.

- [ ] **Step 2: Replace `app/config.py`**

Replace `apps/backend/app/config.py` with:

```python
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    llm_provider: Literal["fake", "ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    report_timezone: str = "America/Port_of_Spain"
    app_env: str = "development"
    dedup_salt: str = "dev-salt-change-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 3: Replace `tests/test_config.py`**

Replace `apps/backend/tests/test_config.py` with:

```python
from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEDUP_SALT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./dev.db"
    assert settings.llm_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "gemma3:4b"
    assert settings.report_timezone == "America/Port_of_Spain"
    assert settings.app_env == "development"
    assert settings.dedup_salt == "dev-salt-change-in-production"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dmcu")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama-host:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEDUP_SALT", "prod-salt-xyz")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dmcu"
    assert settings.llm_provider == "fake"
    assert settings.ollama_base_url == "http://ollama-host:11434"
    assert settings.ollama_model == "gpt-oss:20b"
    assert settings.app_env == "production"
    assert settings.dedup_salt == "prod-salt-xyz"
```

- [ ] **Step 4: Run the config tests**

```bash
cd apps/backend
uv run pytest tests/test_config.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Replace `app/core/llm.py`**

Replace `apps/backend/app/core/llm.py` with:

```python
import json
from typing import Protocol

from langchain_ollama import ChatOllama

from app.config import settings


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_content: str) -> str: ...


class FakeLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses is not None else None

    def generate(self, system_prompt: str, user_content: str) -> str:
        if self._responses is not None:
            if len(self._responses) > 1:
                return self._responses.pop(0)
            return self._responses[0]
        return self._auto_narrative(user_content)

    def _auto_narrative(self, user_content: str) -> str:
        data = json.loads(user_content)
        lines = []
        for fact in data["facts"]:
            unit = fact["unit"] or ""
            title = fact["metric"].replace("_", " ").title()
            lines.append(f"{title}: {fact['value']} {unit} [{fact['citation']['cid']}].")
        return "\n\n".join(lines)


class OllamaLLMClient:
    def __init__(self, base_url: str, model: str, chat: "ChatOllama | None" = None):
        self._chat = chat or ChatOllama(base_url=base_url, model=model)

    def generate(self, system_prompt: str, user_content: str) -> str:
        messages = [("system", system_prompt), ("human", user_content)]
        response = self._chat.invoke(messages)
        return response.content


def get_default_llm_client() -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaLLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)
    return FakeLLMClient()
```

- [ ] **Step 6: Replace `tests/test_llm.py`**

Replace `apps/backend/tests/test_llm.py` with:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.contracts import Citation, Fact, FactTable
from app.core.llm import FakeLLMClient, OllamaLLMClient, get_default_llm_client


def make_fact_table() -> FactTable:
    citation = Citation(
        cid="C001",
        module="survey123",
        description="test",
        query_ref="incident_count()",
        record_ids=["GUID-1"],
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
    )
    fact = Fact(
        metric="incident_count",
        value=19,
        unit="incidents",
        scope={"corporation": "all"},
        breakdown=None,
        verification="validated",
        citation=citation,
    )
    return FactTable(
        request_id="req-1",
        template="test_template",
        params={},
        generated_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        facts=[fact],
        gaps=[],
    )


def test_fake_llm_client_auto_narrative_mode_emits_matching_number_and_citation():
    client = FakeLLMClient()
    fact_table = make_fact_table()

    narrative = client.generate("system prompt", fact_table.model_dump_json())

    assert "19" in narrative
    assert "[C001]" in narrative


def test_fake_llm_client_custom_responses_are_consumed_in_order():
    client = FakeLLMClient(responses=["first", "second"])

    assert client.generate("p", "u") == "first"
    assert client.generate("p", "u") == "second"


def test_fake_llm_client_repeats_final_response_once_queue_has_one_left():
    client = FakeLLMClient(responses=["only"])

    assert client.generate("p", "u") == "only"
    assert client.generate("p", "u") == "only"


def test_ollama_client_generate_calls_chat_correctly():
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "generated narrative"
    mock_chat.invoke.return_value = mock_response

    client = OllamaLLMClient(base_url="http://localhost:11434", model="gemma3:4b", chat=mock_chat)
    result = client.generate("system prompt", "user content")

    assert result == "generated narrative"
    mock_chat.invoke.assert_called_once_with([("system", "system prompt"), ("human", "user content")])


def test_get_default_llm_client_returns_ollama_by_default(monkeypatch):
    monkeypatch.setattr(
        "app.core.llm.settings",
        type(
            "S",
            (),
            {"llm_provider": "ollama", "ollama_base_url": "http://localhost:11434", "ollama_model": "gemma3:4b"},
        )(),
    )

    client = get_default_llm_client()

    assert isinstance(client, OllamaLLMClient)


def test_get_default_llm_client_returns_fake_when_provider_is_fake(monkeypatch):
    monkeypatch.setattr(
        "app.core.llm.settings",
        type(
            "S",
            (),
            {"llm_provider": "fake", "ollama_base_url": "http://localhost:11434", "ollama_model": "gemma3:4b"},
        )(),
    )

    client = get_default_llm_client()

    assert isinstance(client, FakeLLMClient)
```

**Note on `test_get_default_llm_client_returns_ollama_by_default`:** this test does NOT inject a mock `chat` — it exercises the real `OllamaLLMClient.__init__` → real `ChatOllama(...)` construction path, then only asserts `isinstance(client, OllamaLLMClient)`. This is safe and deliberate: `ChatOllama(...)` construction was independently verified during planning to make zero network calls (see Global Constraints), and this test never calls `.generate()`/`.invoke()`, so no real request to `localhost:11434` happens even though Ollama is in fact running on this machine.

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd apps/backend
uv run pytest tests/test_llm.py -v
```

Expected: `6 passed`.

- [ ] **Step 8: Run the full suite**

```bash
cd apps/backend
uv run pytest -v
```

Expected: `181 passed` (same total as before — this is a 1:1 provider substitution, not new functionality).

- [ ] **Step 9: Manual verification against the real local Ollama server**

This is genuinely different from every other manual verification in this project so far — it exercises a real, non-fake LLM completion, not `FakeLLMClient`'s auto-narrative path. Confirm Ollama is running with `gemma3:4b` available first:

```bash
ollama list
```

Expected: `gemma3:4b` appears in the list (already confirmed present on this machine during planning). If it's missing, do not proceed — report back rather than pulling a multi-GB model unprompted.

Then run the actual report generation through the real model:

```bash
cd apps/backend
rm -f dev.db
uv run alembic upgrade head
uv run python cli.py ingest survey123 fixtures/sample_small.csv
uv run python cli.py generate minister_regional_comparison --date-from 2024-06-01 --date-to 2024-06-30
rm -f dev.db
```

Expected: this takes noticeably longer than the fake-client path (several seconds, real model inference) and prints a complete markdown report to stdout with a `# Ministerial Regional Comparison Briefing` heading, a narrative written in the model's own words (not the fake client's templated `"{Metric}: {value} {unit} [{cid}]."` pattern), `## Data Tables`, and a `## Citation Appendix`. The `status:` line on stderr may be `ok` or `needs_review` depending on whether `gemma3:4b` — a genuinely smaller/weaker model than what deployment will use — follows the citation rules correctly on the first or second attempt; either outcome is valid evidence the real integration works, since `needs_review` is exactly the safety behavior this whole system exists to provide. Report which one occurred and, if `needs_review`, include the violations printed to stderr.

- [ ] **Step 10: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/app/config.py \
        apps/backend/app/core/llm.py apps/backend/tests/test_config.py apps/backend/tests/test_llm.py
git commit -m "backend: replace Anthropic LLM client with Ollama (via langchain-ollama)"
```

---

## Definition of Done

- [ ] `cd apps/backend && uv run pytest -v` — all 181 tests pass, 0 failures, no real network calls made by the automated suite.
- [ ] `grep -rln "anthropic" apps/backend --include="*.py"` (excluding `.venv`) returns nothing.
- [ ] Manual verification (Task 1 Step 9) confirms a real `gemma3:4b` completion produces a full markdown report via `cli.py generate`.
