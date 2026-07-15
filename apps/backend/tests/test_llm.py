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
