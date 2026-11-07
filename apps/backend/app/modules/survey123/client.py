import re
from urllib.parse import parse_qs, urlsplit

import httpx

from app.config import settings

DEFAULT_PORTAL_URL = "https://www.arcgis.com"
ITEM_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class Survey123NotConfigured(Exception):
    pass


class Survey123Unavailable(Exception):
    pass


def _client() -> httpx.Client:
    return httpx.Client(timeout=30)


def _survey_location() -> tuple[str, str]:
    """The portal and item id, read from the survey's share link."""
    if settings.survey123_api_key in ("", "none"):
        raise Survey123NotConfigured("SURVEY123_API_KEY is not set")
    url = urlsplit(settings.survey123_api_url)
    item_id = url.path.rstrip("/").rsplit("/", 1)[-1]
    if not ITEM_ID_PATTERN.match(item_id):
        raise Survey123NotConfigured("SURVEY123_API_URL is not a survey share link")
    portal = parse_qs(url.query).get("portalUrl", [DEFAULT_PORTAL_URL])[0]
    return portal.rstrip("/"), item_id


def _get(client: httpx.Client, url: str, params: dict) -> dict:
    # The key goes in a header so it stays out of URLs, logs and httpx errors.
    # Referer is what an allowlist of hosts on the key is checked against.
    # Redirects are not followed: httpx would carry this header to the new host.
    headers = {
        "X-Esri-Authorization": f"Bearer {settings.survey123_api_key}",
        "Referer": settings.app_url,
    }
    try:
        response = client.get(url, params={**params, "f": "json"}, headers=headers)
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise Survey123Unavailable(f"Survey123 request failed: {type(exc).__name__}") from exc
    # ArcGIS puts the reason in the body, under a 200 or a 401 alike, so read it first.
    if "error" in body:
        error = body["error"]
        reason = " ".join([str(error.get("message")), *error.get("details", [])])
        raise Survey123Unavailable(f"Survey123 error {error.get('code')}: {reason}")
    if not response.is_success:
        raise Survey123Unavailable(f"Survey123 returned HTTP {response.status_code}")
    return body


def _feature_service_url(client: httpx.Client, portal: str, item_id: str) -> str:
    """A survey item holds the form. Its responses live in a linked feature service.

    Survey2Data is the view for reading results. Survey2Service is the view the
    form submits through, which usually has querying turned off, so it comes last.
    """
    for relationship in ("Survey2Data", "Survey2Service"):
        body = _get(
            client,
            f"{portal}/sharing/rest/content/items/{item_id}/relatedItems",
            {"relationshipType": relationship, "direction": "forward"},
        )
        for item in body.get("relatedItems", []):
            if item.get("url"):
                return item["url"].rstrip("/")
    raise Survey123Unavailable("Survey has no linked feature service")


def query_responses(where: str, limit: int, offset: int, layer: int) -> dict:
    portal, item_id = _survey_location()
    with _client() as client:
        service_url = _feature_service_url(client, portal, item_id)
        body = _get(
            client,
            f"{service_url}/{layer}/query",
            {
                "where": where,
                "outFields": "*",
                "resultRecordCount": limit,
                "resultOffset": offset,
            },
        )
    return {
        "features": body.get("features", []),
        "has_more": bool(body.get("exceededTransferLimit", False)),
    }
