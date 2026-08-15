"""Application configuration, read from the environment."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SECRET_KEY = "dev-insecure-secret-change-me"


class Config:
    """Runtime settings. Every value can be overridden by an env var."""

    # `or` rather than a default argument: an env var set to the empty string
    # would otherwise produce SECRET_KEY = "", which passes a
    # "did they set it?" check but still makes every flash() raise at runtime.
    SECRET_KEY = os.environ.get("SESSION_SECRET", "").strip() or DEFAULT_SECRET_KEY

    # Absolute path to the SQLite file. In the container this points at the
    # mounted volume (/data/badeel.db) so the database survives redeploys.
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "data" / "badeel.db")
    )

    # Hours ahead of UTC used when rendering timestamps. Saudi Arabia is +03:00
    # year round, so this is a constant rather than a tz database lookup.
    DISPLAY_UTC_OFFSET_HOURS = int(os.environ.get("DISPLAY_UTC_OFFSET_HOURS", "3"))

    # Seconds a write will wait for a competing writer before giving up.
    SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("SQLITE_BUSY_TIMEOUT_MS", "5000"))

    @staticmethod
    def is_using_default_secret() -> bool:
        return Config.SECRET_KEY == DEFAULT_SECRET_KEY
