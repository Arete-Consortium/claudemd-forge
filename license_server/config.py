"""License server configuration from environment variables.

Legacy CMDF_* variables are honored as a fallback for the pre-rebrand
deployment (the Fly app is still named cmdf-license and its secrets were
set with CMDF_* names). Prefer ANMD_* going forward — set those and the
CMDF_* fallback becomes unused automatically.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(primary: str, legacy: str, default: str | None = None) -> str | None:
    """Return primary env var, falling back to legacy, then default."""
    value = os.environ.get(primary)
    if value is not None:
        return value
    value = os.environ.get(legacy)
    if value is not None:
        return value
    return default


def get_admin_secret() -> str:
    """Return the admin bearer token for protected endpoints."""
    return _env("ANMD_ADMIN_SECRET", "CMDF_ADMIN_SECRET", "change-me-in-production") or ""


def get_db_path() -> Path:
    """Return the SQLite database file path."""
    return Path(_env("ANMD_DB_PATH", "CMDF_DB_PATH", "license_server.db") or "license_server.db")


def get_rate_limit_default() -> str:
    """Return the default rate limit string for slowapi."""
    return _env("ANMD_RATE_LIMIT", "CMDF_RATE_LIMIT", "60/minute") or "60/minute"


def get_stripe_secret_key() -> str | None:
    """Return the Stripe secret key (sk_test_... or sk_live_...)."""
    return os.environ.get("STRIPE_SECRET_KEY")


def get_stripe_webhook_secret() -> str | None:
    """Return the Stripe webhook signing secret (whsec_...)."""
    return os.environ.get("STRIPE_WEBHOOK_SECRET")


def get_smtp_host() -> str:
    """Return SMTP host for outbound email."""
    return _env("ANMD_SMTP_HOST", "CMDF_SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"


def get_smtp_port() -> int:
    """Return SMTP port."""
    return int(_env("ANMD_SMTP_PORT", "CMDF_SMTP_PORT", "587") or "587")


def get_smtp_user() -> str | None:
    """Return SMTP username."""
    return _env("ANMD_SMTP_USER", "CMDF_SMTP_USER")


def get_smtp_password() -> str | None:
    """Return SMTP password or app password."""
    return _env("ANMD_SMTP_PASSWORD", "CMDF_SMTP_PASSWORD")


def get_smtp_from() -> str:
    """Return the From: address for outbound email."""
    return _env("ANMD_SMTP_FROM", "CMDF_SMTP_FROM", "noreply@anchormd.dev") or "noreply@anchormd.dev"


def get_aicards_mint_api() -> str:
    """Return the AI Cards minting API base URL."""
    return os.environ.get("AICARDS_MINT_API", "https://aicards-mint.fly.dev")
