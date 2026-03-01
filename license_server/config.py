"""License server configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def get_admin_secret() -> str:
    """Return the admin bearer token for protected endpoints."""
    return os.environ.get("CMDF_ADMIN_SECRET", "change-me-in-production")


def get_db_path() -> Path:
    """Return the SQLite database file path."""
    return Path(os.environ.get("CMDF_DB_PATH", "license_server.db"))


def get_rate_limit_default() -> str:
    """Return the default rate limit string for slowapi."""
    return os.environ.get("CMDF_RATE_LIMIT", "60/minute")
