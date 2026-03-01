"""Pydantic v2 request/response models for the license server."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# --- Requests ---


class ActivateRequest(BaseModel):
    """Request body for POST /v1/activate."""

    email: str
    tier: str = "pro"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidateRequest(BaseModel):
    """Request body for POST /v1/validate."""

    license_key: str
    machine_id: str | None = None


# --- Responses ---


class HealthResponse(BaseModel):
    """Response for GET /v1/health."""

    status: str = "ok"
    version: str
    total_licenses: int = 0
    active_licenses: int = 0


class ActivateResponse(BaseModel):
    """Response for POST /v1/activate."""

    license_key: str
    tier: str
    email: str
    active: bool = True
    created_at: str
    expires_at: str | None = None


class ValidateResponse(BaseModel):
    """Response for POST /v1/validate."""

    valid: bool
    tier: str
    active: bool = False
    email: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: str
    detail: str | None = None
