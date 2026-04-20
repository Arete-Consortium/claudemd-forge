"""Usage tracking — record scans and check quota against tier limits.

Tier limits:
  Free: 1 audit per repo (tracked by repo_fingerprint), 0 deep scans
  Pro:  unlimited audits, 10 deep scans per billing period (calendar month)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from license_server.database import get_connection
from license_server.key_gen import hash_key, validate_key_checksum, validate_key_format
from license_server.models import (
    ErrorResponse,
    UsageCheckRequest,
    UsageRecordRequest,
    UsageResponse,
)
from license_server.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

_db_path_override = None  # Set in tests to override get_connection

# Tier limits per scan type per billing period
TIER_LIMITS: dict[str, dict[str, int]] = {
    "free": {
        "audit": 1,       # 1 per repo (enforced by repo_fingerprint uniqueness)
        "deep_scan": 0,    # no deep scans
    },
    "pro": {
        "audit": -1,       # unlimited (-1)
        "deep_scan": 10,   # 10 per month
    },
}


def _current_period() -> str:
    """Return current billing period as YYYY-MM."""
    return datetime.now(UTC).strftime("%Y-%m")


def _resolve_license(conn, license_key: str, product: str) -> dict | None:
    """Look up a license by key, returns dict with id, tier, or None."""
    product_aliases = [product]
    if product == "anchormd":
        product_aliases.append("claudemd-forge")
    elif product == "claudemd-forge":
        product_aliases.append("anchormd")

    # Validate format + checksum
    format_ok = any(validate_key_format(license_key, p) for p in product_aliases)
    if not format_ok:
        return None
    checksum_ok = any(validate_key_checksum(license_key, p) for p in product_aliases)
    if not checksum_ok:
        return None

    key_h = hash_key(license_key)
    for pname in product_aliases:
        row = conn.execute(
            "SELECT id, tier, active FROM licenses WHERE key_hash = ? AND product = ?",
            (key_h, pname),
        ).fetchone()
        if row is not None:
            if not row["active"]:
                return None
            return {"id": row["id"], "tier": row["tier"]}
    return None


def _get_usage_count(
    conn, license_id: str, scan_type: str, period: str, repo_fingerprint: str | None = None
) -> int:
    """Count scans for a license in the given period."""
    if scan_type == "audit" and repo_fingerprint:
        # Audits are tracked per-repo (not per-period for free tier)
        row = conn.execute(
            "SELECT COUNT(*) FROM scan_usage "
            "WHERE license_id = ? AND scan_type = 'audit' AND repo_fingerprint = ?",
            (license_id, repo_fingerprint),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM scan_usage "
            "WHERE license_id = ? AND scan_type = ? AND period = ?",
            (license_id, scan_type, period),
        ).fetchone()
    return row[0] if row else 0


def _check_quota(
    tier: str, scan_type: str, used: int
) -> tuple[int, int, bool]:
    """Return (limit, remaining, allowed) for a tier + scan type."""
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    limit = limits.get(scan_type, 0)
    if limit == -1:  # unlimited
        return -1, -1, True
    remaining = max(0, limit - used)
    return limit, remaining, remaining > 0


@router.post("/v1/usage/check", response_model=UsageResponse)
@limiter.limit("60/minute")
def check_usage(req: UsageCheckRequest, request: Request) -> UsageResponse:
    """Check remaining scan quota for a license."""
    conn = get_connection(_db_path_override)
    period = _current_period()

    license_info = _resolve_license(conn, req.license_key, req.product)
    if license_info is None:
        # No valid license = free tier
        return UsageResponse(
            scan_type=req.scan_type,
            used=0,
            limit=TIER_LIMITS["free"].get(req.scan_type, 0),
            remaining=TIER_LIMITS["free"].get(req.scan_type, 0),
            period=period,
            allowed=TIER_LIMITS["free"].get(req.scan_type, 0) > 0,
        )

    used = _get_usage_count(conn, license_info["id"], req.scan_type, period)
    limit, remaining, allowed = _check_quota(license_info["tier"], req.scan_type, used)

    return UsageResponse(
        scan_type=req.scan_type,
        used=used,
        limit=limit,
        remaining=remaining,
        period=period,
        allowed=allowed,
    )


@router.post("/v1/usage", response_model=UsageResponse)
@limiter.limit("30/minute")
def record_usage(req: UsageRecordRequest, request: Request) -> UsageResponse | ErrorResponse:
    """Record a scan and return updated quota."""
    conn = get_connection(_db_path_override)
    period = _current_period()

    license_info = _resolve_license(conn, req.license_key, req.product)
    if license_info is None:
        # No valid license = free tier, check free limits
        tier = "free"
        license_id = "free:" + hash_key(req.license_key)[:16]
    else:
        tier = license_info["tier"]
        license_id = license_info["id"]

    # Check quota before recording
    used = _get_usage_count(conn, license_id, req.scan_type, period, req.repo_fingerprint)
    limit, remaining, allowed = _check_quota(tier, req.scan_type, used)

    if not allowed:
        return UsageResponse(
            scan_type=req.scan_type,
            used=used,
            limit=limit,
            remaining=0,
            period=period,
            allowed=False,
        )

    # Record the scan
    conn.execute(
        "INSERT INTO scan_usage (license_id, scan_type, repo_fingerprint, period) "
        "VALUES (?, ?, ?, ?)",
        (license_id, req.scan_type, req.repo_fingerprint, period),
    )
    conn.commit()

    used += 1
    remaining = -1 if limit == -1 else max(0, limit - used)

    return UsageResponse(
        scan_type=req.scan_type,
        used=used,
        limit=limit,
        remaining=remaining,
        period=period,
        allowed=True,
    )
