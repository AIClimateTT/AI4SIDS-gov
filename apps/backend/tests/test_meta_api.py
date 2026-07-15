import pytest
from fastapi.testclient import TestClient

from app.core.contracts import IngestResult, MetricSpec
from app.core.registry import register_module, reset_registry
from app.main import app


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


class FakeModule:
    name = "fake_module"

    def ingest(self, file_path):
        return IngestResult(
            rows_read=0,
            rows_inserted=0,
            rows_updated=0,
            duplicates_flagged=0,
            unmapped_values={},
            pii_columns_dropped=[],
        )

    def list_metrics(self):
        return [
            MetricSpec(
                name="incident_count",
                description="Total incidents, breakdown by incident_type",
                params_schema={"type": "object", "properties": {}},
                module="fake_module",
            )
        ]

    def run_metric(self, name, params, session):
        return []


def test_list_modules_empty():
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    assert response.json() == []


def test_list_modules_returns_registered_module_with_metrics():
    register_module(FakeModule())
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "fake_module"
    assert body[0]["metrics"][0]["name"] == "incident_count"
