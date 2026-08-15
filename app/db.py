"""SQLite connection handling and schema management.

One connection per request, stored on `flask.g` and closed by a teardown hook.
The schema is created on startup and versioned through `PRAGMA user_version`, so
a redeploy against an existing volume upgrades in place instead of failing.
"""

import logging
import sqlite3
from pathlib import Path

import click
from flask import current_app, g

from app.constants import REASONS, STATUSES, STATUS_NEW

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_STATUS_LIST = ", ".join(f"'{status}'" for status in STATUSES)
_REASON_LIST = ", ".join(f"'{reason}'" for reason in REASONS)

# Tables and the plain indexes. Every statement here is unconditionally safe to
# re-run, whatever the data looks like.
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS card_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name   TEXT    NOT NULL,
    employee_number TEXT    NOT NULL,
    hajj_name       TEXT    NOT NULL,
    passport_number TEXT    NOT NULL,
    visa_number     TEXT    NOT NULL,
    request_reason  TEXT    NOT NULL CHECK (request_reason IN ({_REASON_LIST})),
    card_returned   INTEGER NOT NULL DEFAULT 0 CHECK (card_returned IN (0, 1)),
    request_upload  INTEGER NOT NULL DEFAULT 0 CHECK (request_upload IN (0, 1)),
    is_written      INTEGER NOT NULL DEFAULT 0 CHECK (is_written IN (0, 1)),
    status          TEXT    NOT NULL DEFAULT '{STATUS_NEW}'
                            CHECK (status IN ({_STATUS_LIST})),
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_card_requests_created_at
    ON card_requests (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_card_requests_status
    ON card_requests (status);
CREATE INDEX IF NOT EXISTS ix_card_requests_reason
    ON card_requests (request_reason);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

ACTIVE_PASSPORT_INDEX = "ux_card_requests_active_passport"

# At most one open report per passport. This replaces the previous
# check-then-insert, which could admit duplicates under concurrent submissions.
#
# Kept out of SCHEMA on purpose: unlike the statements above, this one is NOT
# unconditionally safe to re-run. `IF NOT EXISTS` only skips the work when the
# index already exists — when it is missing and the existing rows violate it,
# the statement raises. Running it inside the startup executescript would take
# the whole application down at import time, before anyone could log in and fix
# the offending rows.
ACTIVE_PASSPORT_INDEX_SQL = f"""
CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_PASSPORT_INDEX}
    ON card_requests (passport_number)
    WHERE status = '{STATUS_NEW}'
"""


def connect(database_path: str, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    """Open a tuned SQLite connection. Used by the app and by scripts alike."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.row_factory = sqlite3.Row

    # busy_timeout goes first: switching journal modes briefly needs an
    # exclusive lock, so without it a second connection opening at the same
    # moment fails outright instead of waiting.
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")

    # WAL lets the read-heavy pages (employee, admin, statistics) run while a
    # submission is writing, which matters once gunicorn serves several threads.
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> sqlite3.Connection:
    """Return this request's connection, opening one on first use."""
    if "db" not in g:
        g.db = connect(
            current_app.config["DATABASE_PATH"],
            current_app.config["SQLITE_BUSY_TIMEOUT_MS"],
        )
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def duplicate_active_passports(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    """Passports carrying more than one open report, worst first.

    Legacy rows can violate the uniqueness rule, because the old application
    checked for duplicates in Python before inserting and concurrent
    submissions could slip past.
    """
    rows = connection.execute(
        """
        SELECT passport_number, COUNT(*) AS n
        FROM card_requests
        WHERE status = ?
        GROUP BY passport_number
        HAVING n > 1
        ORDER BY n DESC, passport_number
        """,
        (STATUS_NEW,),
    ).fetchall()
    return [(row["passport_number"], row["n"]) for row in rows]


def ensure_active_passport_index(connection: sqlite3.Connection) -> bool:
    """Create the one-open-report-per-passport index if the data allows it.

    Returns True when the index is in place. When existing rows violate it, the
    application logs the offending passports and keeps running without it, so an
    administrator can reach /admin and resolve them. Refusing to boot would make
    the only tool capable of fixing the data unreachable.
    """
    try:
        connection.execute(ACTIVE_PASSPORT_INDEX_SQL)
        return True
    except sqlite3.IntegrityError:
        offenders = duplicate_active_passports(connection)
        logger.error(
            "Could not create %s: %d passport(s) have more than one open report "
            "(%s). Duplicate submissions are NOT being blocked. Close the stale "
            "reports in /admin, then restart.",
            ACTIVE_PASSPORT_INDEX,
            len(offenders),
            ", ".join(f"{passport} x{count}" for passport, count in offenders[:10]),
        )
        return False


def init_schema(connection: sqlite3.Connection) -> bool:
    """Create tables and indexes, then stamp the schema version.

    Safe to call on every boot. Returns whether the uniqueness index is active.
    """
    connection.executescript(SCHEMA)
    index_ready = ensure_active_passport_index(connection)

    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if current_version != SCHEMA_VERSION:
        # PRAGMA does not accept bound parameters, and SCHEMA_VERSION is an
        # int literal defined above, so interpolation is safe here.
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        logger.info(
            "SQLite schema initialised (version %s -> %s)",
            current_version,
            SCHEMA_VERSION,
        )

    return index_ready


def init_app(app) -> None:
    """Wire connection teardown and CLI commands, then build the schema."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    connection = connect(
        app.config["DATABASE_PATH"], app.config["SQLITE_BUSY_TIMEOUT_MS"]
    )
    try:
        init_schema(connection)
    finally:
        connection.close()


@click.command("init-db")
def init_db_command() -> None:
    """Create the SQLite schema without starting the server."""
    init_schema(get_db())
    click.echo(f"Initialised database at {current_app.config['DATABASE_PATH']}")
