import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import create_app
from app.cli import app as cli_app
from app.config import settings
from app.modules.survey123 import client as survey123_client

ITEM_ID = "68834896188a40ab8472f5eefedea1f4"
PORTAL = "https://portal.example.test/portal"
SERVICE = "https://portal.example.test/server/rest/services/Hosted/survey/FeatureServer"
KEY = "test-key-not-real"


def _ok(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/relatedItems"):
        return httpx.Response(200, json={"relatedItems": [{"url": SERVICE}]})
    return httpx.Response(
        200,
        json={"features": [{"attributes": {"objectid": 1}}], "exceededTransferLimit": True},
    )


@pytest.fixture
def use_handler(monkeypatch):
    monkeypatch.setattr(settings, "survey123_api_key", KEY)
    monkeypatch.setattr(
        settings, "survey123_api_url", f"https://survey123.arcgis.com/share/{ITEM_ID}?portalUrl={PORTAL}"
    )
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")

    def install(handler):
        monkeypatch.setattr(
            survey123_client,
            "_client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

    return install


def _get(**params) -> httpx.Response:
    return TestClient(create_app()).get("/field-data/survey123/query", params=params)


def test_query_finds_the_service_through_the_portal_and_returns_features(use_handler):
    seen = []

    def handler(request):
        seen.append(request)
        return _ok(request)

    use_handler(handler)

    response = _get(where="objectid > 0", limit=5, offset=10, layer=1)

    assert response.status_code == 200, response.text
    assert response.json() == {"features": [{"attributes": {"objectid": 1}}], "has_more": True}
    lookup, query = seen
    assert lookup.url.path == f"/portal/sharing/rest/content/items/{ITEM_ID}/relatedItems"
    assert lookup.url.params["relationshipType"] == "Survey2Data"
    assert query.url.path.endswith("/FeatureServer/1/query")
    assert query.url.params["where"] == "objectid > 0"
    assert query.url.params["resultRecordCount"] == "5"
    assert query.url.params["resultOffset"] == "10"


def test_key_travels_only_in_the_header_with_the_app_as_referer(use_handler):
    seen = []

    def handler(request):
        seen.append(request)
        return _ok(request)

    use_handler(handler)

    assert _get().status_code == 200

    for request in seen:
        assert request.headers["X-Esri-Authorization"] == f"Bearer {KEY}"
        assert request.headers["Referer"] == "http://localhost:3000"
        assert KEY not in str(request.url)


def test_query_falls_back_to_the_submission_view_when_no_results_view_is_linked(use_handler):
    relationships = []

    def handler(request):
        if request.url.path.endswith("/relatedItems"):
            relationships.append(request.url.params["relationshipType"])
            if request.url.params["relationshipType"] == "Survey2Data":
                return httpx.Response(200, json={"relatedItems": []})
        return _ok(request)

    use_handler(handler)

    assert _get().status_code == 200
    assert relationships == ["Survey2Data", "Survey2Service"]


@pytest.mark.parametrize("status", [200, 401])
def test_arcgis_error_body_reaches_the_caller_whatever_the_status(use_handler, status):
    use_handler(
        lambda request: httpx.Response(
            status,
            json={
                "error": {
                    "code": 498,
                    "message": "Invalid token.",
                    "details": ["Error validating token: Invalid Referer."],
                }
            },
        )
    )

    response = _get()

    assert response.status_code == 502
    assert (
        response.json()["detail"]
        == "Survey123 error 498: Invalid token. Error validating token: Invalid Referer."
    )


def test_unreachable_portal_becomes_a_502_without_the_key(use_handler):
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    use_handler(handler)

    response = _get()

    assert response.status_code == 502
    assert KEY not in response.text


def test_redirects_are_refused_so_the_key_cannot_follow_them(use_handler):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example.test/"})

    use_handler(handler)

    assert _get().status_code == 502
    assert len(seen) == 1


def test_survey_without_a_linked_service_becomes_a_502(use_handler):
    use_handler(lambda request: httpx.Response(200, json={"relatedItems": []}))

    response = _get()

    assert response.status_code == 502
    assert response.json()["detail"] == "Survey has no linked feature service"


@pytest.mark.parametrize(
    ("key", "url"),
    [
        ("none", f"https://survey123.arcgis.com/share/{ITEM_ID}"),
        (KEY, "https://survey123.arcgis.com/api/v3/surveys"),
    ],
)
def test_missing_configuration_becomes_a_503_without_calling_out(use_handler, monkeypatch, key, url):
    def handler(request):
        raise AssertionError("no request should be sent")

    use_handler(handler)
    monkeypatch.setattr(settings, "survey123_api_key", key)
    monkeypatch.setattr(settings, "survey123_api_url", url)

    assert _get().status_code == 503


def test_limit_is_bounded(use_handler):
    use_handler(_ok)

    assert _get(limit=1001).status_code == 422


def test_cli_check_reports_success_without_printing_responses(use_handler):
    use_handler(_ok)

    result = CliRunner().invoke(cli_app, ["survey123", "check"])

    assert result.exit_code == 0, result.output
    assert "Referer: http://localhost:3000" in result.output
    assert "OK: query returned 1 row(s)" in result.output
    assert "objectid" not in result.output
    assert KEY not in result.output


def test_cli_check_fails_with_the_arcgis_reason(use_handler):
    use_handler(
        lambda request: httpx.Response(
            401, json={"error": {"code": 498, "message": "Invalid token.", "details": []}}
        )
    )

    result = CliRunner().invoke(cli_app, ["survey123", "check"])

    assert result.exit_code == 1
    assert "FAILED: Survey123 error 498: Invalid token." in result.output
    assert KEY not in result.output
