import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_model_json(raw: str) -> dict:
    """The model's JSON object. Small models wrap it in a fence or a sentence
    of preamble; the first complete object in the text is the answer."""
    stripped = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        start = stripped.find("{")
        if start < 0:
            raise ValueError(f"model did not return JSON: {exc}") from exc
        try:
            payload, _end = json.JSONDecoder().raw_decode(stripped[start:])
        except json.JSONDecodeError as inner:
            raise ValueError(f"model did not return JSON: {inner}") from inner
    if not isinstance(payload, dict):
        raise ValueError("model JSON must be an object with incidents and logs")
    return payload
