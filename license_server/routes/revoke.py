"""POST /v1/revoke — Revoke (deactivate) a license key."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from license_server.config import get_admin_secret
from license_server.database import get_connection
from license_server.key_gen import hash_key
from license_server.models import ErrorResponse, RevokeRequest, RevokeResponse
from license_server.rate_limit import limiter

router = APIRouter()

_db_path_override = None


def _require_admin(authorization: str = Header(...)) -> str:
    """Verify Bearer token matches the admin secret."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[len("Bearer ") :]
    if token != get_admin_secret():
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


@router.post(
    "/v1/revoke",
    response_model=RevokeResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def revoke(
    req: RevokeRequest,
    request: Request,
    _token: str = Depends(_require_admin),
) -> RevokeResponse:
    """Revoke a license key. Idempotent — returns 200 even if already revoked."""
    conn = get_connection(_db_path_override)
    client_ip = request.client.host if request.client else "unknown"

    key_h = hash_key(req.license_key)
    row = conn.execute(
        "SELECT license_key_masked, email FROM licenses WHERE key_hash = ?",
        (key_h,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="License key not found")

    revoked_at = datetime.now(UTC).isoformat()

    conn.execute("UPDATE licenses SET active = 0 WHERE key_hash = ?", (key_h,))
    conn.commit()

    # Audit log.
    conn.execute(
        "INSERT INTO validation_log (key_hash, machine_id, result, ip_address) VALUES (?, ?, ?, ?)",
        (key_h, None, "revoked_by_admin", client_ip),
    )
    conn.commit()

    return RevokeResponse(
        revoked=True,
        license_key_masked=row["license_key_masked"],
        email=row["email"],
        revoked_at=revoked_at,
    )
