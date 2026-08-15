#!/usr/bin/env python3
"""One-off import of the Supabase data into the local SQLite database.

Run this once, locally, while the old Supabase project is still reachable, then
copy the resulting file onto the Coolify volume.

    pip install -e '.[migrate]'
    export SUPABASE_URL=... SUPABASE_KEY=...
    python scripts/migrate_from_supabase.py --database data/badeel.db

The script is idempotent: rows are keyed by their original id, so a second run
overwrites rather than duplicates. Pass --dry-run to see the counts first.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.constants import (  # noqa: E402
    REASONS,
    REASON_LOST,
    SETTING_TOTAL_HAJJ,
    STATUSES,
    STATUS_NEW,
)
from app.db import (  # noqa: E402
    ACTIVE_PASSPORT_INDEX,
    connect,
    duplicate_active_passports,
    ensure_active_passport_index,
    init_schema,
)
from app.repository import normalise_passport  # noqa: E402
from app.timeutil import to_utc_iso, utc_now_iso  # noqa: E402

PAGE_SIZE = 1000

REQUEST_COLUMNS = (
    "id",
    "employee_name",
    "employee_number",
    "hajj_name",
    "passport_number",
    "visa_number",
    "request_reason",
    "card_returned",
    "request_upload",
    "is_written",
    "status",
    "created_at",
    "updated_at",
)


def fetch_all_rows(client, table: str) -> list[dict]:
    """Page through a Supabase table.

    The REST API caps a single response at 1000 rows, so an unpaged select
    silently truncates larger tables.
    """
    rows: list[dict] = []
    offset = 0
    while True:
        response = (
            client.table(table)
            .select("*")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        page = response.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def normalise_request(raw: dict) -> dict:
    """Coerce one Supabase row into the SQLite schema's expectations."""
    now = utc_now_iso()

    reason = raw.get("request_reason")
    if reason not in REASONS:
        reason = REASON_LOST

    status = raw.get("status")
    if status not in STATUSES:
        status = STATUS_NEW

    created_at = to_utc_iso(raw.get("created_at")) or now
    updated_at = to_utc_iso(raw.get("updated_at")) or created_at

    return {
        "id": raw.get("id"),
        "employee_name": raw.get("employee_name") or "",
        "employee_number": raw.get("employee_number") or "",
        "hajj_name": raw.get("hajj_name") or "",
        # Folded to the same canonical form the app writes, so legacy rows
        # differing only in case or spacing collapse onto one key.
        "passport_number": normalise_passport(raw.get("passport_number") or ""),
        "visa_number": raw.get("visa_number") or "",
        "request_reason": reason,
        "card_returned": int(bool(raw.get("card_returned"))),
        "request_upload": int(bool(raw.get("request_upload"))),
        "is_written": int(bool(raw.get("is_written"))),
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def import_requests(connection: sqlite3.Connection, rows: list[dict]) -> int:
    placeholders = ", ".join("?" for _ in REQUEST_COLUMNS)
    statement = (
        f"INSERT OR REPLACE INTO card_requests ({', '.join(REQUEST_COLUMNS)}) "
        f"VALUES ({placeholders})"
    )

    imported = 0
    for raw in rows:
        record = normalise_request(raw)
        connection.execute(statement, [record[column] for column in REQUEST_COLUMNS])
        imported += 1
    return imported


def import_settings(connection: sqlite3.Connection, rows: list[dict]) -> int:
    imported = 0
    for raw in rows:
        key = raw.get("key")
        value = raw.get("value")
        if not key or value is None:
            continue
        connection.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(key), str(value)),
        )
        imported += 1
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get("DATABASE_PATH", "data/badeel.db"),
        help="Destination SQLite file (default: data/badeel.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be imported without writing anything",
    )
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("SUPABASE_URL and SUPABASE_KEY must be set.", file=sys.stderr)
        return 2

    try:
        from supabase import create_client
    except ImportError:
        print(
            "The supabase package is not installed. Run: pip install -e '.[migrate]'",
            file=sys.stderr,
        )
        return 2

    client = create_client(supabase_url, supabase_key)

    print("Reading from Supabase...")
    request_rows = fetch_all_rows(client, "card_requests")
    setting_rows = fetch_all_rows(client, "app_settings")
    print(f"  card_requests: {len(request_rows)} rows")
    print(f"  app_settings:  {len(setting_rows)} rows")

    if args.dry_run:
        print("Dry run: nothing written.")
        return 0

    connection = connect(args.database)
    try:
        init_schema(connection)

        # The partial unique index would reject legacy duplicates mid-import.
        # Drop it, load everything, then try to put it back.
        connection.execute(f"DROP INDEX IF EXISTS {ACTIVE_PASSPORT_INDEX}")

        connection.execute("BEGIN")
        try:
            imported_requests = import_requests(connection, request_rows)
            imported_settings = import_settings(connection, setting_rows)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

        print(f"Imported {imported_requests} reports and {imported_settings} settings.")

        if not ensure_active_passport_index(connection):
            duplicates = duplicate_active_passports(connection)
            print(
                "\nWARNING: these passports have more than one open report, so the "
                "uniqueness index was not created:",
                file=sys.stderr,
            )
            for passport, count in duplicates:
                print(f"  - {passport} ({count} بلاغ)", file=sys.stderr)
            print(
                "\nThe database is still usable and the app will start against it, "
                "logging a warning. Resolve these in the admin portal (move the "
                "stale ones off 'New'), then run this script again to finish.",
                file=sys.stderr,
            )
            return 1

        print("Uniqueness index in place. Migration complete.")

        total_hajj = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?", (SETTING_TOTAL_HAJJ,)
        ).fetchone()
        if total_hajj is None:
            print(
                "Note: total_hajj was not present in Supabase; "
                "set it from the admin portal."
            )
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
