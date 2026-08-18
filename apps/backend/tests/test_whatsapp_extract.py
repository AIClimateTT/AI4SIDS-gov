import json

from app.modules.whatsapp.extract import extract_proposals
from app.modules.whatsapp.parse import ParsedMessage, parse_export


class StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.user_contents: list[str] = []
        self.system_prompts: list[str] = []

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.system_prompts.append(system_prompt)
        self.user_contents.append(user_content)
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


def _msg(index: int, body: str, sender: str = "Jane Doe") -> ParsedMessage:
    return ParsedMessage(index=index, timestamp=None, sender=sender, body=body)


CANONICAL = "diego_martin_regional_corporati"

INCIDENT_JSON = json.dumps(
    {
        "incidents": [
            {
                "corporation": CANONICAL,
                "community": "Petit Valley",
                "street": None,
                "incident_type": "flooding_",
                "incident_summary": "3 houses flooded",
                "event_date": "2026-08-15",
                "injuries_count": None,
                "deaths_count": None,
                "source_index": 1,
                "source_quote": "Diego Martin: 3 houses flooded in Petit Valley",
            }
        ],
        "logs": [
            {
                "corporation": CANONICAL,
                "category": "resource",
                "statement": "200 sandbags remaining at depot",
                "item": "sandbags",
                "quantity": 200,
                "unit": "units",
                "status": "available",
                "source_index": 2,
                "source_quote": "200 sandbags remaining at depot",
            }
        ],
    }
)


def test_extract_maps_json_to_proposals():
    llm = StubLLM([INCIDENT_JSON])
    result = extract_proposals(
        [_msg(1, "3 houses flooded"), _msg(2, "200 sandbags remaining")],
        llm,
    )

    assert len(result.incidents) == 1
    assert result.incidents[0].corporation == CANONICAL
    assert result.incidents[0].incident_summary == "3 houses flooded"
    assert result.incidents[0].community == "Petit Valley"
    assert len(result.logs) == 1
    assert result.logs[0].quantity == 200
    assert result.logs[0].item == "sandbags"


def test_unknown_corporation_slug_becomes_null():
    payload = json.dumps(
        {
            "incidents": [
                {
                    "corporation": "not_a_real_corp",
                    "incident_summary": "a tree fell",
                    "source_index": 1,
                    "source_quote": "a tree fell",
                }
            ],
            "logs": [],
        }
    )
    result = extract_proposals([_msg(1, "a tree fell")], StubLLM([payload]))

    assert result.incidents[0].corporation is None
    assert result.incidents[0].incident_summary == "a tree fell"


def test_strips_markdown_fences_around_json():
    fenced = "```json\n" + INCIDENT_JSON + "\n```"
    result = extract_proposals([_msg(1, "3 houses flooded")], StubLLM([fenced]))

    assert len(result.incidents) == 1
    assert len(result.logs) == 1


def test_user_content_sent_to_llm_has_no_raw_phones():
    messages = parse_export(
        "[15/08/2026, 14:32:10] Jane Doe: call +1 868-555-1234 about flooding\n"
    )
    llm = StubLLM(['{"incidents": [], "logs": []}'])

    extract_proposals(messages, llm)

    assert llm.user_contents
    blob = "\n".join(llm.user_contents)
    assert "+1 868-555-1234" not in blob
    assert "868-555-1234" not in blob
    assert "5551234" not in blob
    assert "[phone]" in blob


def test_chunks_long_transcripts_and_concatenates_proposals():
    first = json.dumps(
        {
            "incidents": [
                {
                    "corporation": CANONICAL,
                    "incident_summary": "from chunk 1",
                    "source_index": 1,
                    "source_quote": "from chunk 1",
                }
            ],
            "logs": [],
        }
    )
    second = json.dumps(
        {
            "incidents": [],
            "logs": [
                {
                    "corporation": CANONICAL,
                    "category": "activity",
                    "statement": "from chunk 2",
                    "source_index": 2,
                    "source_quote": "from chunk 2",
                }
            ],
        }
    )
    llm = StubLLM([first, second])
    # Bodies large enough that two messages cannot share a 12k chunk.
    messages = [
        _msg(1, "A" * 8000),
        _msg(2, "B" * 8000),
    ]

    result = extract_proposals(messages, llm)

    assert len(llm.user_contents) == 2
    assert [i.incident_summary for i in result.incidents] == ["from chunk 1"]
    assert [log.statement for log in result.logs] == ["from chunk 2"]
