import json
from datetime import datetime

from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet
from app.modules.capture.turn import apply_turn, missing_fields


class StubLLM:
    def __init__(self, response: str):
        self.response = response
        self.user_contents: list[str] = []

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.user_contents.append(user_content)
        return self.response


def empty_working_set() -> CaptureWorkingSet:
    return CaptureWorkingSet(
        as_at=datetime(2026, 8, 18, 14, 0),
        alert_level="none",
        present_activity=None,
        situation_overview=None,
        incidents=[],
        logs=[],
    )


def test_turn_extracts_incident_and_log_and_summarizes():
    response = json.dumps(
        {
            "assistant_message": (
                "Captured: flooding of 5 houses in Petit Valley, no injuries. "
                "200 sandbags remaining at the depot. What was the date?"
            ),
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "alert_level": "yellow",
                "present_activity": "Adverse weather response",
                "situation_overview": None,
                "incidents": [
                    {
                        "row_id": "1",
                        "community": "Petit Valley",
                        "incident_type": "flooding",
                        "incident_summary": "5 houses flooded",
                        "injuries_count": 0,
                        "deaths_count": 0,
                    }
                ],
                "logs": [
                    {
                        "category": "resource",
                        "statement": "200 sandbags remaining at depot",
                        "item": "sandbags",
                        "quantity": 200,
                        "unit": "bags",
                        "status": "available",
                    }
                ],
            },
        }
    )

    working, message, missing, _messages = apply_turn(
        empty_working_set(),
        [],
        "Yellow alert. 5 houses flooded in Petit Valley, no injuries. 200 sandbags remaining at depot.",
        StubLLM(response),
    )

    assert "5 houses" in message
    assert working.alert_level == "yellow"
    assert working.incidents[0].community == "Petit Valley"
    assert working.incidents[0].incident_type == "flooding_"
    assert working.incidents[0].injuries_count == 0
    assert working.logs[0].quantity == 200
    assert any("date" in item.message.lower() for item in missing)


def test_correction_turn_replaces_count():
    prior = CaptureWorkingSet(
        as_at=datetime(2026, 8, 18, 14, 0),
        alert_level="yellow",
        incidents=[
            CaptureIncident(
                row_id="1",
                community="Petit Valley",
                incident_type="flooding_",
                incident_summary="3 houses flooded",
                injuries_count=0,
                deaths_count=0,
            )
        ],
        logs=[],
    )
    response = json.dumps(
        {
            "assistant_message": "Updated: 5 houses flooded in Petit Valley, not 3.",
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "alert_level": "yellow",
                "incidents": [
                    {
                        "row_id": "1",
                        "community": "Petit Valley",
                        "incident_type": "flooding_",
                        "incident_summary": "5 houses flooded",
                        "injuries_count": 0,
                        "deaths_count": 0,
                    }
                ],
                "logs": [],
            },
        }
    )

    working, message, _, _ = apply_turn(
        prior,
        [],
        "wait not 3 houses, 5",
        StubLLM(response),
    )

    assert working.incidents[0].incident_summary == "5 houses flooded"
    assert "3 houses flooded" not in (working.incidents[0].incident_summary or "")
    assert "5" in message


def test_invented_quantity_not_in_user_text_is_dropped():
    response = json.dumps(
        {
            "assistant_message": "Noted flooding in Petit Valley.",
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "alert_level": "none",
                "incidents": [
                    {
                        "row_id": "1",
                        "community": "Petit Valley",
                        "incident_type": "flooding_",
                        "incident_summary": "houses flooded",
                        "injuries_count": 12,
                    }
                ],
                "logs": [
                    {
                        "category": "resource",
                        "statement": "sandbags at depot",
                        "item": "sandbags",
                        "quantity": 500,
                        "unit": "bags",
                    }
                ],
            },
        }
    )

    working, _, _, _ = apply_turn(
        empty_working_set(),
        [],
        "Flooding in Petit Valley. Sandbags at the depot.",
        StubLLM(response),
    )

    assert working.incidents[0].injuries_count is None
    assert working.logs[0].quantity is None


def test_number_already_on_working_set_is_kept():
    prior = CaptureWorkingSet(
        as_at=datetime(2026, 8, 18, 14, 0),
        incidents=[
            CaptureIncident(row_id="1", incident_summary="5 houses flooded", injuries_count=0)
        ],
        logs=[
            CaptureLog(
                category="resource",
                statement="200 sandbags remaining",
                item="sandbags",
                quantity=200,
                unit="bags",
            )
        ],
    )
    response = json.dumps(
        {
            "assistant_message": "Still 200 sandbags. Adding a fallen tree on Morne Coco Road.",
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "incidents": [
                    {
                        "row_id": "1",
                        "incident_summary": "5 houses flooded",
                        "injuries_count": 0,
                    },
                    {
                        "row_id": "2",
                        "street": "Morne Coco Road",
                        "incident_type": "fallen tree",
                        "incident_summary": "Fallen tree blocking the road",
                    },
                ],
                "logs": [
                    {
                        "category": "resource",
                        "statement": "200 sandbags remaining",
                        "item": "sandbags",
                        "quantity": 200,
                        "unit": "bags",
                    }
                ],
            },
        }
    )

    working, _, _, _ = apply_turn(
        prior,
        [],
        "Also a fallen tree on Morne Coco Road.",
        StubLLM(response),
    )

    assert working.logs[0].quantity == 200
    assert working.incidents[0].injuries_count == 0
    assert working.incidents[1].incident_type == "fallen_tree"


def test_missing_fields_ask_for_date_type_and_casualties():
    missing = missing_fields(
        CaptureWorkingSet(
            as_at=datetime(2026, 8, 18, 14, 0),
            incidents=[
                CaptureIncident(row_id="1", incident_summary="houses flooded")
            ],
            logs=[],
        )
    )

    texts = " ".join(item.message.lower() for item in missing)
    assert "date" in texts
    assert "type" in texts
    assert "injur" in texts or "casualt" in texts or "death" in texts


def test_assigns_row_id_when_model_omits_it():
    response = json.dumps(
        {
            "assistant_message": "Captured a fallen tree.",
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "incidents": [
                    {
                        "incident_summary": "Fallen tree",
                        "incident_type": "fallen_tree",
                    }
                ],
                "logs": [],
            },
        }
    )

    working, _, _, _ = apply_turn(
        empty_working_set(),
        [],
        "Fallen tree on the main road.",
        StubLLM(response),
    )

    assert working.incidents[0].row_id == "1"


class StreamingStubLLM:
    def __init__(self, response: str, chunk_size: int = 8):
        self.response = response
        self.chunk_size = chunk_size

    def generate(self, system_prompt: str, user_content: str) -> str:
        return self.response

    def generate_stream(self, system_prompt: str, user_content: str):
        text = self.response
        for start in range(0, len(text), self.chunk_size):
            yield text[start : start + self.chunk_size]


def test_stream_turn_emits_assistant_message_before_working_set_is_complete():
    from app.modules.capture.turn import TurnComplete, stream_turn

    response = json.dumps(
        {
            "assistant_message": "Captured: 5 houses flooded.",
            "capture": {
                "as_at": "2026-08-18T14:00:00",
                "alert_level": "yellow",
                "incidents": [
                    {
                        "row_id": "1",
                        "community": "Petit Valley",
                        "incident_type": "flooding",
                        "incident_summary": "5 houses flooded",
                        "injuries_count": 0,
                    }
                ],
                "logs": [],
            },
        }
    )

    events = list(
        stream_turn(
            empty_working_set(),
            [],
            "5 houses flooded in Petit Valley",
            StreamingStubLLM(response, chunk_size=12),
        )
    )

    text_chunks = [event for event in events if isinstance(event, str)]
    dones = [event for event in events if isinstance(event, TurnComplete)]
    assert "".join(text_chunks) == "Captured: 5 houses flooded."
    assert len(text_chunks) > 1
    assert len(dones) == 1
    assert dones[0].working.incidents[0].community == "Petit Valley"
    assert dones[0].working.alert_level == "yellow"


def test_extract_assistant_message_grows_as_json_arrives():
    from app.modules.capture.stream_json import AssistantMessageExtractor

    extractor = AssistantMessageExtractor()
    seen = ""
    payload = '{"assistant_message": "Hello there", "capture": {}}'
    for start in range(0, len(payload), 7):
        seen += extractor.feed(payload[start : start + 7])
    assert seen == "Hello there"

