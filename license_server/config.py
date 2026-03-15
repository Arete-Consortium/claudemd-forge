"""License server configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def get_admin_secret() -> str:
    """Return the admin bearer token for protected endpoints."""
    return os.environ.get("ANMD_ADMIN_SECRET", "change-me-in-production")


def get_db_path() -> Path:
    """Return the SQLite database file path."""
    return Path(os.environ.get("ANMD_DB_PATH", "license_server.db"))


def get_rate_limit_default() -> str:
    """Return the default rate limit string for slowapi."""
    return os.environ.get("ANMD_RATE_LIMIT", "60/minute")


def get_stripe_secret_key() -> str | None:
    """Return the Stripe secret key (sk_test_... or sk_live_...)."""
    return os.environ.get("STRIPE_SECRET_KEY")


def get_stripe_webhook_secret() -> str | None:
    """Return the Stripe webhook signing secret (whsec_...)."""
    return os.environ.get("STRIPE_WEBHOOK_SECRET")


def get_smtp_host() -> str:
    """Return SMTP host for outbound email."""
    return os.environ.get("ANMD_SMTP_HOST", "smtp.gmail.com")


def get_smtp_port() -> int:
    """Return SMTP port."""
    return int(os.environ.get("ANMD_SMTP_PORT", "587"))


def get_smtp_user() -> str | None:
    """Return SMTP username."""
    return os.environ.get("ANMD_SMTP_USER")


def get_smtp_password() -> str | None:
    """Return SMTP password or app password."""
    return os.environ.get("ANMD_SMTP_PASSWORD")


def get_smtp_from() -> str:
    """Return the From: address for outbound email."""
    return os.environ.get("ANMD_SMTP_FROM", "noreply@anchormd.dev")
