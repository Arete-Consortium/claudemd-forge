"""POST /v1/validate — Validate a license key and track machine."""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from license_server.database import get_connection
from license_server.key_gen import hash_key, validate_key_checksum, validate_key_format
from license_server.models import ValidateRequest, ValidateResponse
from license_server.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

_db_path_override = None


def _log_validation(conn, key_hash: str, machine_id: str | None, result: str, ip: str) -> None:
    """Append to the validation audit trail."""
    conn.execute(
        "INSERT INTO validation_log (key_hash, machine_id, result, ip_address) VALUES (?, ?, ?, ?)",
        (key_hash, machine_id, result, ip),
    )
    conn.commit()


def _track_machine(conn, license_id: str, machine_id: str) -> None:
    """Insert or update a machine activation record."""
    existing = conn.execute(
        "SELECT id FROM machine_activations WHERE license_id = ? AND machine_id = ?",
        (license_id, machine_id),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE machine_activations SET last_seen = datetime('now') "
            "WHERE license_id = ? AND machine_id = ?",
            (license_id, machine_id),
        )
    else:
        conn.execute(
            "INSERT INTO machine_activations (license_id, machine_id) VALUES (?, ?)",
            (license_id, machine_id),
        )
    conn.commit()


@router.post("/v1/validate", response_model=ValidateResponse)
@limiter.limit("60/minute")
def validate(req: ValidateRequest, request: Request) -> ValidateResponse:
    """Validate a license key, optionally tracking the machine."""
    conn = get_connection(_db_path_override)
    client_ip = request.client.host if request.client else "unknown"

    # Determine which product names to check (current + legacy alias).
    product_aliases = [req.product]
    if req.product == "anchormd":
        product_aliases.append("claudemd-forge")
    elif req.product == "claudemd-forge":
        product_aliases.append("anchormd")

    # Format check — try the requested product, then its alias.
    format_ok = any(
        validate_key_format(req.license_key, p) for p in product_aliases
    )
    if not format_ok:
        key_h = hash_key(req.license_key)
        _log_validation(conn, key_h, req.machine_id, "invalid_format", client_ip)
        return ValidateResponse(valid=False, tier="free", product=req.product)

    # Checksum check — try both salts.
    checksum_ok = any(
        validate_key_checksum(req.license_key, p) for p in product_aliases
    )
    if not checksum_ok:
        key_h = hash_key(req.license_key)
        _log_validation(conn, key_h, req.machine_id, "invalid_checksum", client_ip)
        return ValidateResponse(valid=False, tier="free", product=req.product)

    # Lookup by hash — try all product aliases.
    key_h = hash_key(req.license_key)
    row = None
    for product_name in product_aliases:
        row = conn.execute(
            "SELECT id, tier, email, active, expires_at, metadata, product "
            "FROM licenses WHERE key_hash = ? AND product = ?",
            (key_h, product_name),
        ).fetchone()
        if row is not None:
            break

    if row is None:
        _log_validation(conn, key_h, req.machine_id, "not_found", client_ip)
        return ValidateResponse(valid=False, tier="free", product=req.product)

    # Check active status.
    if not row["active"]:
        _log_validation(conn, key_h, req.machine_id, "revoked", client_ip)
        return ValidateResponse(valid=False, tier="free", product=req.product, active=False)

    # Check expiry.
    expires_at = row["expires_at"]
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if datetime.now(UTC) > exp:
                _log_validation(conn, key_h, req.machine_id, "expired", client_ip)
                return ValidateResponse(
                    valid=False, tier="free", product=req.product, expires_at=expires_at
                )
        except ValueError:
            pass  # Malformed date — treat as non-expired

    # Track machine if provided.
    if req.machine_id:
        _track_machine(conn, row["id"], req.machine_id)

    _log_validation(conn, key_h, req.machine_id, "valid", client_ip)

    metadata = {}
    if row["metadata"]:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            metadata = json.loads(row["metadata"])

    return ValidateResponse(
        valid=True,
        tier=row["tier"],
        product=row["product"],
        active=True,
        email=row["email"],
        expires_at=row["expires_at"],
        metadata=metadata,
    )
