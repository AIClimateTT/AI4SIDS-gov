import json


def _find_unescaped_quote(raw: str) -> int | None:
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            return index
    return None


def _decode_json_string_prefix(raw: str) -> str:
    candidate = raw
    if candidate.endswith("\\"):
        candidate = candidate[:-1]
    while candidate:
        try:
            return json.loads(f'"{candidate}"')
        except json.JSONDecodeError:
            candidate = candidate[:-1]
            if candidate.endswith("\\"):
                candidate = candidate[:-1]
    return ""


class AssistantMessageExtractor:
    """Incrementally pull the JSON string value of assistant_message from a growing buffer."""

    def __init__(self) -> None:
        self._buf = ""
        self._emitted = 0
        self._value_start: int | None = None
        self._done = False

    def feed(self, chunk: str) -> str:
        if self._done or not chunk:
            return ""
        self._buf += chunk
        if self._value_start is None and not self._locate_value_start():
            return ""

        raw = self._buf[self._value_start :]
        end = _find_unescaped_quote(raw)
        if end is not None:
            decoded = json.loads(f'"{raw[:end]}"')
            self._done = True
        else:
            decoded = _decode_json_string_prefix(raw)
        newly = decoded[self._emitted :]
        self._emitted = len(decoded)
        return newly

    def _locate_value_start(self) -> bool:
        key = '"assistant_message"'
        idx = self._buf.find(key)
        if idx < 0:
            return False
        cursor = idx + len(key)
        while cursor < len(self._buf) and self._buf[cursor] in " \t\n\r":
            cursor += 1
        if cursor >= len(self._buf) or self._buf[cursor] != ":":
            return False
        cursor += 1
        while cursor < len(self._buf) and self._buf[cursor] in " \t\n\r":
            cursor += 1
        if cursor >= len(self._buf) or self._buf[cursor] != '"':
            return False
        self._value_start = cursor + 1
        return True
