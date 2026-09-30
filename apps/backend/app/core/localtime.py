"""One place that knows the difference between UTC and Trinidad time.

Timestamps (submitted, edited, ingested) are stored as UTC and converted here
when a person needs to read them or group them by day. Calendar dates (date of
event, assessment date) are stored as plain dates and never converted: the
19th of April is the 19th of April in every timezone.
"""

from datetime import date, datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.config import settings


@lru_cache
def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.report_timezone)


def as_utc(value: datetime) -> datetime:
    """An aware UTC datetime. A naive value is taken to already be UTC, which
    is how SQLite hands back a timezone-aware column."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_wall_clock_to_utc(value: datetime) -> datetime:
    """A naive reading off a Trinidad clock, as UTC."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=local_tz()).astimezone(timezone.utc)


def to_local(value: datetime) -> datetime:
    return as_utc(value).astimezone(local_tz())


def local_date(value: datetime) -> date:
    """The Trinidad calendar day a moment fell on. Group by this, never by
    value.date(), or anything after 8 PM lands on the next day."""
    return to_local(value).date()
