from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.contracts import Citation, Fact, FactTable, IngestResult, MetricSpec


def make_citation(**overrides) -> Citation:
    defaults = dict(
        cid="S123-001",
        module="survey123",
        description="Survey123 incidents, Sangre Grande, 2026-01-01 to 2026-01-31",
        query_ref="incidents_by_corporation(corporation=sangre_grande, date_from=2026-01-01, date_to=2026-01-31)",
        record_ids=["GUID-1", "GUID-2"],
        as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Citation(**defaults)


def test_citation_round_trips_through_json():
    citation = make_citation()

    restored = Citation.model_validate_json(citation.model_dump_json())

    assert restored == citation


def test_citation_allows_null_record_ids_above_cap():
    citation = make_citation(record_ids=None)

    assert citation.record_ids is None


def test_fact_accepts_validated_verification_and_nested_citation():
    fact = Fact(
        metric="homes_affected_count",
        value=42,
        unit="incidents",
        scope={"corporation": "sangre_grande", "window": "2026-01-01..2026-01-31"},
        breakdown={"validated": 40, "pending": 2},
        verification="validated",
        citation=make_citation(),
    )

    assert fact.citation.cid == "S123-001"
    assert fact.breakdown == {"validated": 40, "pending": 2}


def test_fact_rejects_invalid_verification_literal():
    with pytest.raises(ValidationError):
        Fact(
            metric="homes_affected_count",
            value=42,
            unit=None,
            scope={},
            breakdown=None,
            verification="confirmed",
            citation=make_citation(),
        )


def test_fact_table_collects_facts_and_gaps():
    table = FactTable(
        request_id="req-001",
        template="minister_regional_comparison",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        facts=[
            Fact(
                metric="homes_affected_count",
                value=42,
                unit="incidents",
                scope={"corporation": "sangre_grande"},
                breakdown=None,
                verification="validated",
                citation=make_citation(),
            )
        ],
        gaps=["No data for Tobago corporations in this window"],
    )

    assert len(table.facts) == 1
    assert table.gaps == ["No data for Tobago corporations in this window"]


def test_metric_spec_carries_params_schema():
    spec = MetricSpec(
        name="incidents_by_corporation",
        description="Counts per corporation, including the (no corporation recorded) bucket",
        params_schema={
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
            },
        },
        module="survey123",
    )

    assert spec.module == "survey123"
    assert spec.params_schema["type"] == "object"


def test_ingest_result_reports_unmapped_values_and_dropped_pii_columns():
    result = IngestResult(
        rows_read=14942,
        rows_inserted=14942,
        rows_updated=0,
        duplicates_flagged=17,
        unmapped_values={"Municipal Boundary": ["Unknown_Corp_Typo"]},
        pii_columns_dropped=[
            "Name of Person",
            "Contact Information",
            "Identification Card Number",
            "Name of Second Person",
            "Second Contact Information",
            "Second Identification Card Number",
            "Please list the names of the occupants and their relation",
        ],
    )

    assert result.rows_read == 14942
    assert "Identification Card Number" in result.pii_columns_dropped
