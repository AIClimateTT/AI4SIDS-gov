import json

from app.modules.whatsapp.adjust import adjust_working_set
from app.modules.whatsapp.extract import DraftIncident, DraftLog

CORP = "diego_martin_regional_corporati"


class StubLLM:
    def __init__(self, response: str):
        self.response = response
        self.user_contents: list[str] = []

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.user_contents.append(user_content)
        return self.response


def test_adjust_replaces_working_set_from_json():
    response = json.dumps(
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
    incidents, logs = adjust_working_set(
        [
            DraftIncident(
                corporation=CORP,
                incident_summary="3 houses flooded",
                source_index=1,
                source_quote="3 houses flooded",
                included=True,
            )
        ],
        [],
        "use the later correction of 5 houses",
        StubLLM(response),
    )

    assert incidents[0].incident_summary == "5 houses flooded"
    assert logs == []


def test_adjust_unknown_corp_becomes_null():
    response = json.dumps(
        {
            "incidents": [
                {
                    "corporation": "not_a_real_corp",
                    "incident_summary": "a tree fell",
                    "source_index": 1,
                    "source_quote": "a tree fell",
                    "included": True,
                }
            ],
            "logs": [],
        }
    )
    incidents, _ = adjust_working_set(
        [
            DraftIncident(
                corporation=None,
                incident_summary="a tree fell",
                source_index=1,
                source_quote="a tree fell",
                included=False,
            )
        ],
        [],
        "leave unattributed",
        StubLLM(response),
    )

    assert incidents[0].corporation is None
    assert incidents[0].included is False


def test_adjust_requires_instruction():
    try:
        adjust_working_set([], [], "  ", StubLLM("{}"))
    except ValueError as exc:
        assert "instruction" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
