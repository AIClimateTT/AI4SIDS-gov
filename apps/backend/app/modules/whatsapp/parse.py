import re
from dataclasses import dataclass
from datetime import datetime

# WhatsApp inserts these around timestamps and senders. Strip before matching.
_LTR = "\u200e"
_RTL = "\u200f"

# [15/08/2026, 14:32:10] Sender: body  — seconds optional
_BRACKET_LINE = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+(.+)$"
)
# 15/08/2026, 14:32 - Sender: body
_DASH_LINE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+-\s+(.+)$"
)

# Phones, not dates (slashes) or times (colons).
_PHONE_RE = re.compile(
    r"""
    (?:
        \+\d[\d\s().-]{6,}\d
        |
        (?<!\d)\d{3}[\s.-]\d{3}[\s.-]\d{4}(?!\d)
        |
        (?<!\d)\d{10,15}(?!\d)
    )
    """,
    re.VERBOSE,
)

_ENCRYPTED_MARKER = "messages and calls are end-to-end encrypted"


@dataclass(frozen=True)
class ParsedMessage:
    index: int
    timestamp: datetime | None
    sender: str
    body: str


def redact_phones(text: str) -> tuple[str, bool]:
    """Replace phone-like tokens with [phone]. Dates and times are left alone."""
    redacted, count = _PHONE_RE.subn("[phone]", text)
    return redacted, count > 0


def _parse_datetime(date_s: str, time_s: str) -> datetime | None:
    date_fmt = "%d/%m/%Y" if len(date_s.split("/")[-1]) == 4 else "%d/%m/%y"
    time_fmt = "%H:%M:%S" if time_s.count(":") == 2 else "%H:%M"
    try:
        return datetime.strptime(f"{date_s} {time_s}", f"{date_fmt} {time_fmt}")
    except ValueError:
        return None


def _split_sender_body(rest: str) -> tuple[str, str] | None:
    # First colon separates sender from body. System lines have no colon.
    if ": " not in rest and not rest.endswith(":"):
        return None
    sender, _, body = rest.partition(":")
    sender = sender.strip()
    body = body.strip()
    if not sender:
        return None
    return sender, body


def _match_header(line: str) -> tuple[datetime | None, str, str] | None:
    for pattern in (_BRACKET_LINE, _DASH_LINE):
        match = pattern.match(line)
        if match is None:
            continue
        timestamp = _parse_datetime(match.group(1), match.group(2))
        split = _split_sender_body(match.group(3))
        if split is None:
            return None
        sender, body = split
        return timestamp, sender, body
    return None


def parse_export(text: str) -> list[ParsedMessage]:
    """Split a WhatsApp .txt export into redacted messages."""
    cleaned = text.replace("\ufeff", "").replace(_LTR, "").replace(_RTL, "")
    messages: list[ParsedMessage] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        sender, _ = redact_phones(current["sender"])
        body, _ = redact_phones(current["body"])
        messages.append(
            ParsedMessage(
                index=len(messages) + 1,
                timestamp=current["timestamp"],
                sender=sender,
                body=body,
            )
        )
        current = None

    for raw in cleaned.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _ENCRYPTED_MARKER in line.lower():
            continue
        header = _match_header(line)
        if header is not None:
            flush()
            timestamp, sender, body = header
            current = {"timestamp": timestamp, "sender": sender, "body": body}
            continue
        if current is not None:
            current["body"] = f"{current['body']}\n{line}"

    flush()
    return messages
