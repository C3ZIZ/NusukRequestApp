"""Timestamp helpers.

Timestamps are stored in UTC as ISO 8601 strings. Storing a single offset keeps
`ORDER BY created_at` correct, since SQLite compares those columns as text and a
mix of `+00:00` and `+03:00` rows would sort by the wrong instant. Conversion to
Riyadh time happens on the way out, for display only.
"""

from datetime import datetime, timedelta, timezone

from app.config import Config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current time as a UTC ISO 8601 string, e.g. 2025-08-16T01:31:00+00:00."""
    return utc_now().isoformat()


def to_utc_iso(value: str | datetime | None) -> str | None:
    """Normalise an arbitrary timestamp to a UTC ISO 8601 string.

    Naive values are assumed to already be UTC. Returns None for input that
    cannot be parsed, so callers can decide on a fallback.
    """
    if value is None:
        return None

    if isinstance(value, str):
        parsed = parse_iso(value)
        if parsed is None:
            return None
    else:
        parsed = value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime | None:
    """Parse an ISO 8601 string, tolerating the trailing `Z` form."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def to_display_tz(value: datetime | str | None) -> datetime | None:
    """Convert a stored UTC timestamp into the configured display timezone."""
    if value is None:
        return None

    parsed = parse_iso(value) if isinstance(value, str) else value
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    display_tz = timezone(timedelta(hours=Config.DISPLAY_UTC_OFFSET_HOURS))
    return parsed.astimezone(display_tz)
