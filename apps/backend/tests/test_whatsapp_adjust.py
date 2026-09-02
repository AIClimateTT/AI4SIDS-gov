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


def _incident(**overrides) -> DraftIncident:
    base = dict(
        corporation=CORP,
        incident_summary="flooding on Main Street",
        source_index=1,
        source_quote="flooding on Main Street",
        included=True,
    )
    base.update(overrides)
    return DraftIncident(**base)


def _response(incident_fields: dict | None = None, logs: list | None = None) -> str:
    incident = {
        "corporation": CORP,
        "incident_summary": "flooding on Main Street",
        "source_index": 1,
        "source_quote": "flooding on Main Street",
        "included": True,
    }
    incident.update(incident_fields or {})
    return json.dumps({"incidents": [incident], "logs": logs or []})


def test_adjust_drops_a_casualty_figure_the_model_invented():
    """
    The draft carries no injuries and the officer's instruction names no
    number, so a figure appearing in the model's reply came from nowhere.
    Promotion writes these rows into sitrep_incidents, the authoritative
    table, so an invented figure here reaches the minister's report as a
    corporation's own count.
    """
    incidents, _ = adjust_working_set(
        [_incident()],
        [],
        "attribute this to Diego Martin",
        StubLLM(_response({"injuries_count": 7})),
    )

    assert incidents[0].injuries_count is None


def test_adjust_keeps_a_figure_the_officer_typed():
    incidents, _ = adjust_working_set(
        [_incident()],
        [],
        "record 4 injuries for this incident",
        StubLLM(_response({"injuries_count": 4})),
    )

    assert incidents[0].injuries_count == 4


def test_adjust_keeps_a_figure_already_on_the_draft():
    """Re-stating an existing count is not invention, even unprompted."""
    incidents, _ = adjust_working_set(
        [_incident(deaths_count=2)],
        [],
        "fix the street name",
        StubLLM(_response({"deaths_count": 2})),
    )

    assert incidents[0].deaths_count == 2


def test_adjust_keeps_zero_as_none_occurred():
    incidents, _ = adjust_working_set(
        [_incident()],
        [],
        "confirm no casualties",
        StubLLM(_response({"deaths_count": 0})),
    )

    assert incidents[0].deaths_count == 0


def test_adjust_drops_an_invented_log_quantity():
    log = DraftLog(
        corporation=CORP,
        statement="hampers distributed",
        source_index=2,
        source_quote="hampers distributed",
        included=True,
    )
    _, logs = adjust_working_set(
        [],
        [log],
        "mark this as relief supplied",
        StubLLM(
            json.dumps(
                {
                    "incidents": [],
                    "logs": [
                        {
                            "corporation": CORP,
                            "statement": "hampers distributed",
                            "quantity": 250,
                            "source_index": 2,
                            "source_quote": "hampers distributed",
                            "included": True,
                        }
                    ],
                }
            )
        ),
    )

    assert logs[0].quantity is None
