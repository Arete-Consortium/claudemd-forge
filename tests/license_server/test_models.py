"""Tests for Pydantic request/response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from license_server.models import (
    ActivateRequest,
    ActivateResponse,
    ErrorResponse,
    HealthResponse,
    ValidateRequest,
    ValidateResponse,
)


class TestActivateRequest:
    def test_minimal(self) -> None:
        req = ActivateRequest(email="test@example.com")
        assert req.email == "test@example.com"
        assert req.tier == "pro"
        assert req.product == "anchormd"
        assert req.metadata == {}

    def test_with_tier(self) -> None:
        req = ActivateRequest(email="t@t.com", tier="free")
        assert req.tier == "free"

    def test_with_product(self) -> None:
        req = ActivateRequest(email="t@t.com", product="agent-lint")
        assert req.product == "agent-lint"

    def test_with_metadata(self) -> None:
        req = ActivateRequest(email="t@t.com", metadata={"org": "acme"})
        assert req.metadata["org"] == "acme"

    def test_missing_email_raises(self) -> None:
        with pytest.raises(ValidationError):
            ActivateRequest()


class TestValidateRequest:
    def test_minimal(self) -> None:
        req = ValidateRequest(license_key="ANMD-ABCD-EFGH-32E3")
        assert req.license_key == "ANMD-ABCD-EFGH-32E3"
        assert req.product == "anchormd"
        assert req.machine_id is None

    def test_with_machine_id(self) -> None:
        req = ValidateRequest(license_key="ANMD-ABCD-EFGH-32E3", machine_id="abc123")
        assert req.machine_id == "abc123"

    def test_with_product(self) -> None:
        req = ValidateRequest(license_key="ANMD-ABCD-EFGH-32E3", product="agent-lint")
        assert req.product == "agent-lint"

    def test_missing_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            ValidateRequest()


class TestHealthResponse:
    def test_defaults(self) -> None:
        resp = HealthResponse(version="0.1.0")
        assert resp.status == "ok"
        assert resp.total_licenses == 0
        assert resp.active_licenses == 0

    def test_with_counts(self) -> None:
        resp = HealthResponse(version="0.1.0", total_licenses=5, active_licenses=3)
        assert resp.total_licenses == 5
        assert resp.active_licenses == 3


class TestActivateResponse:
    def test_required_fields(self) -> None:
        resp = ActivateResponse(
            license_key="ANMD-ABCD-EFGH-32E3",
            tier="pro",
            product="anchormd",
            email="t@t.com",
            created_at="2026-03-01T00:00:00",
        )
        assert resp.license_key == "ANMD-ABCD-EFGH-32E3"
        assert resp.product == "anchormd"
        assert resp.active is True
        assert resp.expires_at is None


class TestValidateResponse:
    def test_invalid(self) -> None:
        resp = ValidateResponse(valid=False, tier="free")
        assert resp.valid is False
        assert resp.active is False
        assert resp.email is None

    def test_valid(self) -> None:
        resp = ValidateResponse(
            valid=True,
            tier="pro",
            active=True,
            email="t@t.com",
        )
        assert resp.valid is True
        assert resp.metadata == {}


class TestErrorResponse:
    def test_minimal(self) -> None:
        resp = ErrorResponse(error="not_found")
        assert resp.error == "not_found"
        assert resp.detail is None

    def test_with_detail(self) -> None:
        resp = ErrorResponse(error="bad_key", detail="Invalid format")
        assert resp.detail == "Invalid format"
