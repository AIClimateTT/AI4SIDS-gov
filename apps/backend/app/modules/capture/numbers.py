import re

_NUMBER_RE = re.compile(
    r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])"
)

QUANTITY_FIELDS = (
    "injuries_count",
    "deaths_count",
    "special_needs_occupants",
    "estimated_damage_cost",
    "quantity",
)


def extract_numbers(text: str) -> set[float]:
    found: set[float] = set()
    for match in _NUMBER_RE.finditer(text or ""):
        token = match.group(0).replace(",", "")
        try:
            found.add(float(token))
        except ValueError:
            continue
    return found


def numbers_from_working_set(payload: dict) -> set[float]:
    found: set[float] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                if key in QUANTITY_FIELDS and isinstance(inner, (int, float)):
                    found.add(float(inner))
                else:
                    walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(payload)
    return found


def strip_invented_numbers(payload: dict, allowed: set[float]) -> dict:
    def allowed_number(value: object) -> bool:
        if not isinstance(value, (int, float)):
            return False
        # Zero means "none occurred" and is never an invented count.
        if float(value) == 0:
            return True
        return float(value) in allowed

    def walk(value: object) -> object:
        if isinstance(value, dict):
            cleaned: dict = {}
            for key, inner in value.items():
                if key in QUANTITY_FIELDS and isinstance(inner, (int, float)):
                    cleaned[key] = inner if allowed_number(inner) else None
                else:
                    cleaned[key] = walk(inner)
            return cleaned
        if isinstance(value, list):
            return [walk(inner) for inner in value]
        return value

    return walk(payload)
