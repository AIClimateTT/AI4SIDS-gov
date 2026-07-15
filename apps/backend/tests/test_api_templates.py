import pytest
from fastapi.testclient import TestClient

from app.core.registry import reset_registry, reset_template_registry
from app.main import create_app


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    reset_template_registry()
    yield
    reset_registry()
    reset_template_registry()


def test_get_templates_returns_both_real_templates():
    app = create_app()
    client = TestClient(app)

    response = client.get("/templates")

    assert response.status_code == 200
    body = response.json()
    names = {t["name"] for t in body}
    assert names == {"minister_regional_comparison", "single_region_report"}


def test_get_templates_includes_params_with_required_flags():
    app = create_app()
    client = TestClient(app)

    response = client.get("/templates")

    body = response.json()
    minister = next(t for t in body if t["name"] == "minister_regional_comparison")
    param_names = {p["name"] for p in minister["params"]}
    assert param_names == {"date_from", "date_to"}
    assert all(p["required"] for p in minister["params"])
