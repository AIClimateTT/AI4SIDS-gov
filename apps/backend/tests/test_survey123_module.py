import pytest
from fastapi.testclient import TestClient

from app.core.registry import get_module, reset_registry
from app.main import create_app
from app.modules.survey123.module import survey123_module


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def test_survey123_module_has_correct_name():
    assert survey123_module.name == "survey123"


def test_survey123_module_list_metrics_is_empty():
    assert survey123_module.list_metrics() == []


def test_survey123_module_run_metric_raises_for_unknown_metric():
    with pytest.raises(ValueError, match="incident_count"):
        survey123_module.run_metric("incident_count", {}, session=None)


def test_create_app_registers_survey123_module():
    create_app()

    assert get_module("survey123") is survey123_module


def test_modules_endpoint_includes_survey123_after_create_app():
    app = create_app()
    client = TestClient(app)

    response = client.get("/modules")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "survey123"
    assert body[0]["metrics"] == []
