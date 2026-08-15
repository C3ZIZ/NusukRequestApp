"""Data access for card requests and application settings.

Every SQL statement in the application lives here. Routes deal in plain dicts
and never see a cursor, which keeps the request handlers readable and lets the
tests exercise storage without spinning up Flask.
"""

import sqlite3

from app.constants import (
    REASON_DAMAGED,
    SETTING_TOTAL_HAJJ,
    STATUS_CARD_DELIVERED,
    STATUS_CARD_RECEIVED,
    STATUS_FOUND,
    STATUS_NEW,
    REASON_LOST,
)
from app.db import get_db
from app.timeutil import to_display_tz, utc_now_iso

# Boolean-ish columns an admin can toggle from the dashboard. Membership in this
# set is what authorises a column name to be interpolated into the UPDATE below.
TOGGLEABLE_FLAGS = frozenset({"card_returned", "request_upload", "is_written"})

_COLUMNS = """
    id, employee_name, employee_number, hajj_name, passport_number,
    visa_number, request_reason, card_returned, request_upload, is_written,
    status, created_at, updated_at
"""


class DuplicateActiveRequestError(Exception):
    """Raised when a passport already has an open report."""

    def __init__(self, passport_number: str = ""):
        super().__init__(passport_number)
        self.passport_number = passport_number


def normalise_passport(passport_number: str) -> str:
    """Fold a hand-typed passport number to a single canonical form.

    Passport numbers are alphanumeric and entered by hand, and SQLite compares
    text byte-for-byte. Without this, `a1234567`, `A1234567` and `A123 4567`
    are three different keys, and each one could open its own report for the
    same pilgrim despite the uniqueness index.
    """
    return "".join(passport_number.split()).upper()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a row into the shape the templates expect.

    Integer flags become real booleans and timestamps become timezone-aware
    datetimes in the display timezone, so templates can call `.strftime()`
    and use plain truthiness checks.
    """
    record = dict(row)

    for flag in ("card_returned", "request_upload", "is_written"):
        if flag in record:
            record[flag] = bool(record[flag])

    for field in ("created_at", "updated_at"):
        if field in record:
            record[field] = to_display_tz(record[field])

    return record


def list_requests() -> list[dict]:
    """All reports, newest first."""
    rows = get_db().execute(
        f"SELECT {_COLUMNS} FROM card_requests ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_request(request_id: int) -> dict | None:
    row = get_db().execute(
        f"SELECT {_COLUMNS} FROM card_requests WHERE id = ?", (request_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def has_active_request(passport_number: str) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM card_requests WHERE passport_number = ? AND status = ? LIMIT 1",
        (normalise_passport(passport_number), STATUS_NEW),
    ).fetchone()
    return row is not None


def create_request(
    *,
    employee_name: str,
    employee_number: str,
    hajj_name: str,
    passport_number: str,
    visa_number: str,
    request_reason: str,
    card_returned: bool = False,
) -> int:
    """Insert a new report and return its id.

    Raises DuplicateActiveRequestError if the passport already has an open
    report. The database enforces this, so two concurrent submissions cannot
    both succeed.
    """
    now = utc_now_iso()
    passport = normalise_passport(passport_number)
    try:
        cursor = get_db().execute(
            """
            INSERT INTO card_requests (
                employee_name, employee_number, hajj_name, passport_number,
                visa_number, request_reason, card_returned, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_name,
                employee_number,
                hajj_name,
                passport,
                visa_number,
                request_reason,
                int(bool(card_returned)),
                STATUS_NEW,
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError as exc:
        # The same exception class covers CHECK violations, so only treat a
        # passport uniqueness failure as a duplicate and let the rest surface.
        if "passport_number" in str(exc):
            raise DuplicateActiveRequestError(passport) from exc
        raise

    return int(cursor.lastrowid)


def update_status(request_id: int, status: str) -> bool:
    """Set a report's status. Returns False if no such report exists.

    Moving a closed report back to 'New' can collide with the one-open-report
    index if the passport was reported again in the meantime. That is a
    conflict the admin needs explained, not a system error, so it is raised as
    DuplicateActiveRequestError rather than left as a raw IntegrityError.
    """
    try:
        cursor = get_db().execute(
            "UPDATE card_requests SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now_iso(), request_id),
        )
    except sqlite3.IntegrityError as exc:
        if "passport_number" in str(exc):
            existing = get_request(request_id)
            raise DuplicateActiveRequestError(
                existing["passport_number"] if existing else ""
            ) from exc
        raise

    return cursor.rowcount > 0


def update_flag(request_id: int, field: str, value: bool) -> bool:
    """Toggle one of the boolean columns. Returns False if no such report.

    `field` is validated against TOGGLEABLE_FLAGS before it reaches the query,
    so the interpolated column name can only ever be one of three literals.
    """
    if field not in TOGGLEABLE_FLAGS:
        raise ValueError(f"Unknown flag: {field}")

    cursor = get_db().execute(
        f"UPDATE card_requests SET {field} = ?, updated_at = ? WHERE id = ?",
        (int(bool(value)), utc_now_iso(), request_id),
    )
    return cursor.rowcount > 0


def get_statistics() -> dict:
    """Report counts in a single pass over the table.

    Previously this ran six separate `SELECT *` queries and counted the rows in
    Python, which both transferred every row and silently capped at the API's
    default page size.
    """
    row = get_db().execute(
        """
        SELECT
            COUNT(*)                                                AS total_requests,
            SUM(CASE WHEN request_reason = ? THEN 1 ELSE 0 END)     AS total_lost,
            SUM(CASE WHEN request_reason = ? THEN 1 ELSE 0 END)     AS total_damaged,
            SUM(CASE WHEN request_upload = 1 THEN 1 ELSE 0 END)     AS total_uploaded,
            SUM(CASE WHEN is_written = 1 THEN 1 ELSE 0 END)         AS total_written,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)             AS total_delivered,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)             AS total_received,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)             AS total_found,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)             AS total_new
        FROM card_requests
        """,
        (
            REASON_LOST,
            REASON_DAMAGED,
            STATUS_CARD_DELIVERED,
            STATUS_CARD_RECEIVED,
            STATUS_FOUND,
            STATUS_NEW,
        ),
    ).fetchone()

    # SUM() over zero rows yields NULL rather than 0.
    return {key: (row[key] or 0) for key in row.keys()}


def get_setting(key: str, default: str | None = None) -> str | None:
    row = get_db().execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    get_db().execute(
        """
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
    )


def get_total_hajj() -> int:
    """Total arriving pilgrims, or 0 when unset or corrupt."""
    raw = get_setting(SETTING_TOTAL_HAJJ)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def set_total_hajj(value: int) -> None:
    set_setting(SETTING_TOTAL_HAJJ, str(int(value)))
