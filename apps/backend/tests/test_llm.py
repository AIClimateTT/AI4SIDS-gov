from datetime import datetime, timezone
from unittest.mock import MagicMock
import json

from app.core.contracts import Citation, Fact, FactTable
from app.core.llm import (
    FakeLLMClient,
    NimLLMClient,
    OllamaLLMClient,
    get_default_llm_client,
    get_llm_client,
)


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
            {"llm_provider": "ollama", "ollama_base_url": "http://localhost:11434", "ollama_model": "gpt-oss:20b", "ollama_chat_model": "gemma3:4b", "ollama_num_ctx": 8192},
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
            {"llm_provider": "fake", "ollama_base_url": "http://localhost:11434", "ollama_model": "gemma3:4b", "ollama_chat_model": "gemma3:4b", "ollama_num_ctx": 8192},
        )(),
    )

    client = get_default_llm_client()

    assert isinstance(client, FakeLLMClient)


def test_ollama_client_sets_an_explicit_context_window():
    # Ollama defaults num_ctx to 2048. A fact table of ~2,049 tokens silently
    # produced an empty narrative, which the checker then passed as "ok".
    from app.config import settings
    from app.core.llm import OllamaLLMClient

    client = OllamaLLMClient(base_url="http://localhost:11434", model="gemma3:4b")

    assert client._chat.num_ctx == settings.ollama_num_ctx


def test_default_context_window_is_large_enough_for_a_real_fact_table():
    from app.config import Settings

    assert Settings().ollama_num_ctx >= 8192


def _ollama_settings():
    return type(
        "S",
        (),
        {
            "llm_provider": "ollama",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "gpt-oss:20b",
            "ollama_chat_model": "gemma3:4b",
            "ollama_num_ctx": 8192,
        },
    )()


def test_get_llm_client_batch_uses_the_report_model(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", _ollama_settings())

    client = get_llm_client("batch")

    assert isinstance(client, OllamaLLMClient)
    assert client._model == "gpt-oss:20b"


def test_get_llm_client_chat_uses_the_chat_model(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", _ollama_settings())

    client = get_llm_client("chat")

    assert isinstance(client, OllamaLLMClient)
    assert client._model == "gemma3:4b"


def test_fake_llm_client_generate_stream_yields_the_response_in_chunks():
    client = FakeLLMClient(responses=['{"assistant_message": "hello"}'])

    chunks = list(client.generate_stream("p", "u"))

    assert "".join(chunks) == '{"assistant_message": "hello"}'
    assert len(chunks) > 1


def test_ollama_client_generate_stream_yields_chat_chunks():
    mock_chat = MagicMock()
    first = MagicMock()
    first.content = '{"assistant'
    second = MagicMock()
    second.content = '_message": "hi"}'
    mock_chat.stream.return_value = [first, second]

    client = OllamaLLMClient(base_url="http://localhost:11434", model="gemma3:4b", chat=mock_chat)
    chunks = list(client.generate_stream("system prompt", "user content"))

    assert chunks == ['{"assistant', '_message": "hi"}']
    mock_chat.stream.assert_called_once_with(
        [("system", "system prompt"), ("human", "user content")]
    )


def test_get_default_llm_client_is_the_batch_client(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", _ollama_settings())

    client = get_default_llm_client()

    assert isinstance(client, OllamaLLMClient)
    assert client._model == "gpt-oss:20b"


def test_fake_llm_client_returns_extract_json_for_a_whatsapp_transcript():
    raw = FakeLLMClient().generate(
        "system prompt",
        "[1] paste: Diego Martin: 5 houses flooded on Main Rd.",
    )
    parsed = json.loads(raw)
    assert parsed["incidents"][0]["source_index"] == 1
    assert "5 houses" in parsed["incidents"][0]["incident_summary"]
    assert parsed["incidents"][0]["corporation"] is None


def test_fake_llm_client_returns_whatsapp_turn_json_for_a_draft_payload():
    payload = json.dumps(
        {
            "working": {
                "as_at": "2026-08-15T16:00:00",
                "incidents": [
                    {
                        "row_id": "1",
                        "corporation": None,
                        "incident_summary": "3 houses flooded",
                        "source_index": 1,
                        "source_quote": "3 houses flooded",
                        "included": False,
                    }
                ],
                "logs": [],
                "manual_fields": [],
            },
            "missing": [],
            "source_kind": "paste",
            "source": "Diego Martin: 3 houses flooded",
            "messages": [],
            "user_message": "Diego Martin not Siparia",
        }
    )

    raw = FakeLLMClient().generate("system prompt", payload)
    parsed = json.loads(raw)

    assert parsed["assistant_message"]
    assert parsed["working"]["incidents"][0]["corporation"] == (
        "diego_martin_regional_corporati"
    )
    assert parsed["working"]["incidents"][0]["included"] is True


def test_fake_llm_client_returns_canned_capture_json_for_a_capture_payload():
    payload = json.dumps(
        {
            "capture": {"as_at": None, "alert_level": "none", "incidents": [], "logs": []},
            "missing": [],
            "messages": [],
            "user_message": "5 houses flooded in Petit Valley",
        }
    )

    raw = FakeLLMClient().generate("system prompt", payload)
    parsed = json.loads(raw)

    assert parsed["assistant_message"]
    assert "capture" in parsed
    assert isinstance(parsed["capture"]["incidents"], list)


def test_nim_client_generate_calls_chat_correctly():
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "generated narrative"
    mock_chat.invoke.return_value = mock_response

    client = NimLLMClient(
        base_url="http://nim-prod:8000",
        model="openai/gpt-oss-20b",
        api_key="none",
        chat=mock_chat,
    )
    result = client.generate("system prompt", "user content")

    assert result == "generated narrative"
    mock_chat.invoke.assert_called_once_with(
        [("system", "system prompt"), ("human", "user content")]
    )


def test_nim_client_generate_stream_yields_chat_chunks():
    mock_chat = MagicMock()
    first = MagicMock()
    first.content = '{"assistant'
    second = MagicMock()
    second.content = '_message": "hi"}'
    mock_chat.stream.return_value = [first, second]

    client = NimLLMClient(
        base_url="http://nim-prod:8000",
        model="openai/gpt-oss-20b",
        api_key="none",
        chat=mock_chat,
    )
    chunks = list(client.generate_stream("system prompt", "user content"))

    assert chunks == ['{"assistant', '_message": "hi"}']
    mock_chat.stream.assert_called_once_with(
        [("system", "system prompt"), ("human", "user content")]
    )


def _nim_settings():
    return type(
        "S",
        (),
        {
            "llm_provider": "nim",
            "nim_base_url": "http://nim-prod:8000",
            "nim_api_key": "none",
            "nim_model": "openai/gpt-oss-20b",
            "nim_chat_model": "openai/gpt-oss-20b",
        },
    )()


def test_get_llm_client_nim_batch_uses_the_batch_model(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", _nim_settings())

    client = get_llm_client("batch")

    assert isinstance(client, NimLLMClient)
    assert client._model == "openai/gpt-oss-20b"


def test_get_llm_client_nim_chat_uses_the_chat_model(monkeypatch):
    monkeypatch.setattr(
        "app.core.llm.settings",
        type(
            "S",
            (),
            {
                "llm_provider": "nim",
                "nim_base_url": "http://nim-prod:8000",
                "nim_api_key": "none",
                "nim_model": "openai/gpt-oss-20b",
                "nim_chat_model": "openai/gpt-oss-20b-chat",
            },
        )(),
    )

    client = get_llm_client("chat")

    assert isinstance(client, NimLLMClient)
    assert client._model == "openai/gpt-oss-20b-chat"
