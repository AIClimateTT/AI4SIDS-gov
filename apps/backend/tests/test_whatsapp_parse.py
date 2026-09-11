from datetime import datetime

from app.modules.whatsapp.parse import messages_from_source, parse_export, redact_phones


BRACKET_EXPORT = """\
[15/08/2026, 14:32:10] Jane Doe: Diego Martin: 3 houses flooded in Petit Valley
[15/08/2026, 14:33:02] John Smith: Sangre Grande — 200 sandbags remaining at depot
"""

DASH_EXPORT = """\
15/08/2026, 14:32 - Jane Doe: Diego Martin: 3 houses flooded
15/08/2026, 14:33 - John Smith: 200 sandbags remaining
"""

ENCRYPTED_LINE = (
    "Messages and calls are end-to-end encrypted. No one outside of this chat, "
    "not even WhatsApp, can read or listen to them."
)


def test_parses_bracket_timestamps():
    messages = parse_export(BRACKET_EXPORT)

    assert len(messages) == 2
    assert messages[0].index == 1
    assert messages[0].timestamp == datetime(2026, 8, 15, 14, 32, 10)
    assert messages[0].sender == "Jane Doe"
    assert "Petit Valley" in messages[0].body
    assert messages[1].index == 2
    assert messages[1].sender == "John Smith"


def test_parses_dash_timestamps():
    messages = parse_export(DASH_EXPORT)

    assert len(messages) == 2
    assert messages[0].timestamp == datetime(2026, 8, 15, 14, 32)
    assert messages[0].sender == "Jane Doe"
    assert messages[1].timestamp == datetime(2026, 8, 15, 14, 33)
    assert "sandbags" in messages[1].body


def test_folds_continuation_lines_into_previous_body():
    text = (
        "[15/08/2026, 14:32:10] Jane Doe: First line\n"
        "still the same message\n"
        "[15/08/2026, 14:33:00] John Smith: Next\n"
    )

    messages = parse_export(text)

    assert len(messages) == 2
    assert messages[0].body == "First line\nstill the same message"
    assert messages[1].body == "Next"


def test_skips_encrypted_chat_system_line():
    text = ENCRYPTED_LINE + "\n" + BRACKET_EXPORT

    messages = parse_export(text)

    assert len(messages) == 2
    assert all("encrypted" not in m.body.lower() for m in messages)


def test_redacts_phones_in_body():
    text = (
        "[15/08/2026, 14:32:10] Jane Doe: Call the depot at +1 868-555-1234 "
        "or 8685559876 if needed\n"
    )

    messages = parse_export(text)

    assert messages[0].body == "Call the depot at [phone] or [phone] if needed"
    assert "+1 868-555-1234" not in messages[0].body
    assert "8685559876" not in messages[0].body


def test_redacts_numeric_sender():
    text = "[15/08/2026, 14:32:10] +1 868-555-0001: 200 sandbags at the depot\n"

    messages = parse_export(text)

    assert messages[0].sender == "[phone]"
    assert "868" not in messages[0].sender
    assert "sandbags" in messages[0].body


def test_redact_phones_leaves_dates_and_times_alone():
    redacted, changed = redact_phones("as at 15/08/2026 14:32:10 — 200 sandbags")

    assert changed is False
    assert redacted == "as at 15/08/2026 14:32:10 — 200 sandbags"


def test_empty_export_returns_no_messages():
    assert parse_export("") == []
    assert parse_export("   \n\n") == []


def test_messages_from_source_keeps_a_bracket_export():
    messages, kind, pii = messages_from_source(BRACKET_EXPORT)
    assert kind == "export"
    assert pii is False
    assert len(messages) == 2
    assert messages[0].sender == "Jane Doe"


def test_messages_from_source_wraps_free_text_as_one_paste_message():
    text = "Diego Martin: 5 houses flooded on Main Rd. Siparia standing by."
    messages, kind, pii = messages_from_source(text)
    assert kind == "paste"
    assert pii is False
    assert len(messages) == 1
    assert messages[0].index == 1
    assert messages[0].sender == "paste"
    assert messages[0].timestamp is None
    assert "5 houses" in messages[0].body


def test_messages_from_source_redacts_phones_in_pasted_text():
    messages, kind, pii = messages_from_source(
        "Call +1 868-555-1234 about the depot"
    )
    assert kind == "paste"
    assert pii is True
    assert "[phone]" in messages[0].body
    assert "868-555-1234" not in messages[0].body


def test_messages_from_source_empty_text_returns_no_messages():
    messages, kind, pii = messages_from_source("   \n")
    assert messages == []
    assert kind == "paste"
    assert pii is False
