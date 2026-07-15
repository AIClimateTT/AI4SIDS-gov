from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.contracts import Citation, Fact, FactTable
from app.core.llm import AnthropicLLMClient, FakeLLMClient, get_default_llm_client


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


def test_anthropic_client_generate_calls_sdk_correctly():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="generated narrative")]
    mock_client.messages.create.return_value = mock_response

    client = AnthropicLLMClient(api_key="fake-key", model="claude-sonnet-5", client=mock_client)
    result = client.generate("system prompt", "user content")

    assert result == "generated narrative"
    mock_client.messages.create.assert_called_once_with(
        model="claude-sonnet-5",
        max_tokens=4096,
        system="system prompt",
        messages=[{"role": "user", "content": "user content"}],
    )


def test_get_default_llm_client_returns_fake_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings", type("S", (), {"anthropic_api_key": None, "anthropic_model": "claude-sonnet-5"})())

    client = get_default_llm_client()

    assert isinstance(client, FakeLLMClient)


def test_get_default_llm_client_returns_anthropic_when_api_key_set(monkeypatch):
    monkeypatch.setattr(
        "app.core.llm.settings",
        type("S", (), {"anthropic_api_key": "sk-test-123", "anthropic_model": "claude-sonnet-5"})(),
    )

    client = get_default_llm_client()

    assert isinstance(client, AnthropicLLMClient)
