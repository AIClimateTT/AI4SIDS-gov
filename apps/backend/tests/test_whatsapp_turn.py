import json
from datetime import datetime

from app.modules.whatsapp.extract import DraftIncident, WhatsAppWorkingSet
from app.modules.whatsapp.turn import apply_turn, coerce_working_set

CORP = "diego_martin_regional_corporati"
SOURCE = (
    "[15/08/2026, 14:32:10] Jane Doe: Diego Martin: 3 houses flooded in Petit Valley\n"
    "[15/08/2026, 14:33:02] John Smith: 200 sandbags remaining at depot\n"
)


class StubLLM:
    def __init__(self, response: str):
        self.response = response
        self.user_contents: list[str] = []
        self.system_prompts: list[str] = []

    def generate(self, system_prompt: str, user_content: str) -> str:
        self.system_prompts.append(system_prompt)
        self.user_contents.append(user_content)
        return self.response


def _incident(**overrides) -> DraftIncident:
    base = dict(
        row_id="1",
        corporation=CORP,
        incident_summary="3 houses flooded",
        source_index=1,
        source_quote="3 houses flooded in Petit Valley",
        included=True,
    )
    base.update(overrides)
    return DraftIncident(**base)


def _working(**overrides) -> WhatsAppWorkingSet:
    base = dict(
        as_at=datetime(2026, 8, 15, 16, 0),
        incidents=[_incident()],
        logs=[],
        manual_fields=[],
    )
    base.update(overrides)
    return WhatsAppWorkingSet(**base)


def _turn_json(incident_fields: dict | None = None, **extra) -> str:
    incident = {
        "row_id": "1",
        "corporation": CORP,
        "incident_summary": "3 houses flooded",
        "source_index": 1,
        "source_quote": "3 houses flooded in Petit Valley",
        "included": True,
    }
    incident.update(incident_fields or {})
    payload = {
        "assistant_message": extra.pop("assistant_message", "Updated."),
        "working": {
            "as_at": "2026-08-15T16:00:00",
            "incidents": [incident],
            "logs": extra.pop("logs", []),
        },
    }
    payload.update(extra)
    return json.dumps(payload)


def test_turn_updates_rows():
    working, message, _missing, messages = apply_turn(
        _working(),
        [],
        "Diego Martin, not Siparia. Use 5 houses not 3.",
        StubLLM(
            _turn_json(
                {
                    "incident_summary": "5 houses flooded",
                    "source_quote": "not 3, 5 houses",
                },
                assistant_message="Updated to 5 houses in Diego Martin.",
            )
        ),
        source_text=SOURCE,
        source_kind="export",
    )

    assert "5 houses" in message
    assert working.incidents[0].incident_summary == "5 houses flooded"
    assert working.incidents[0].row_id == "1"
    assert messages[-1].role == "assistant"


def test_turn_keeps_a_figure_present_in_source_text():
    working, _, _, _ = apply_turn(
        _working(),
        [],
        "keep the sandbag count on this incident as a note",
        StubLLM(_turn_json({"injuries_count": 200})),
        source_text=SOURCE,
        source_kind="export",
    )
    assert working.incidents[0].injuries_count == 200


def test_turn_strips_a_figure_in_neither_source_working_set_nor_message():
    working, _, _, _ = apply_turn(
        _working(),
        [],
        "attribute this to Diego Martin",
        StubLLM(_turn_json({"injuries_count": 7})),
        source_text=SOURCE,
        source_kind="export",
    )
    assert working.incidents[0].injuries_count is None


def test_turn_pins_manual_corporation():
    prior = _working(
        incidents=[_incident(corporation=CORP)],
        manual_fields=["incident:1.corporation"],
    )
    working, _, _, _ = apply_turn(
        prior,
        [],
        "this is Siparia",
        StubLLM(_turn_json({"corporation": "siparia_regional_corporation"})),
        source_text=SOURCE,
        source_kind="export",
    )
    assert working.incidents[0].corporation == CORP
    assert working.manual_fields == ["incident:1.corporation"]


def test_turn_rejects_empty_message():
    try:
        apply_turn(_working(), [], "  ", StubLLM("{}"), source_text=SOURCE)
    except ValueError as exc:
        assert "message" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_turn_prompt_includes_source_and_does_not_shrink_allowed_set():
    llm = StubLLM(_turn_json())
    apply_turn(
        _working(),
        [],
        "fix the street name",
        llm,
        source_text=SOURCE,
        source_kind="export",
    )
    sent = json.loads(llm.user_contents[0])
    assert sent["source_kind"] == "export"
    assert "3 houses" in sent["source"]
    assert sent["user_message"] == "fix the street name"


def test_coerce_accepts_legacy_adjust_shape():
    previous = _working()
    parsed = {
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
    next_working = coerce_working_set(parsed, previous)
    assert next_working.incidents[0].incident_summary == "5 houses flooded"
    assert next_working.incidents[0].row_id == "1"


def test_model_null_corporation_forces_included_false():
    previous = _working()
    parsed = {
        "working": {
            "incidents": [
                {
                    "row_id": "1",
                    "corporation": None,
                    "incident_summary": "a tree fell",
                    "source_index": 1,
                    "source_quote": "a tree fell",
                    "included": True,
                }
            ],
            "logs": [],
        }
    }
    next_working = coerce_working_set(parsed, previous)
    assert next_working.incidents[0].corporation is None
    assert next_working.incidents[0].included is False


def test_truncated_source_in_prompt_still_allows_numbers_from_full_source():
    huge = "hello " * 4000 + "count is 87 casualties\n"
    working, _, _, _ = apply_turn(
        _working(),
        [],
        "record the casualties from the hour",
        StubLLM(_turn_json({"injuries_count": 87})),
        source_text=huge,
        source_kind="paste",
    )
    assert working.incidents[0].injuries_count == 87
    llm = StubLLM(_turn_json())
    apply_turn(
        _working(),
        [],
        "ok",
        llm,
        source_text=huge,
        source_kind="paste",
    )
    sent = json.loads(llm.user_contents[0])
    assert len(sent["source"]) <= 12_000 + 50
