import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_model_json(raw: str) -> dict:
    stripped = raw.strip()
    stripped = _FENCE_RE.sub("", stripped).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("model JSON must be an object with incidents and logs")
    return payload
