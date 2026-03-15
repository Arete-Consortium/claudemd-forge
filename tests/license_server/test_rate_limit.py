"""Rate limiting tests — verify slowapi wiring on all endpoints."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from license_server import main as main_module
from license_server.database import run_migrations
from license_server.main import app
from license_server.rate_limit import limiter


@pytest.fixture
def db(tmp_path):
    """In-memory SQLite database with migrations applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn)
    return conn


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Ensure limiter is enabled and storage is clean for each test."""
    limiter.enabled = True
    limiter._storage.storage.clear()
    yield
    limiter._storage.storage.clear()


@pytest.fixture
def rate_limited_client(db, monkeypatch):
    """TestClient with rate limiting ENABLED."""
    monkeypatch.setattr(main_module, "_db_path_override", ":memory:")

    def _get_test_conn(db_path=None):
        return db

    monkeypatch.setattr("license_server.main.get_connection", _get_test_conn)
    monkeypatch.setattr("license_server.database._connection", db)

    with TestClient(app) as c:
        yield c


class TestActivateRateLimit:
    """POST /v1/activate — 10/minute."""

    def test_activate_under_limit(self, rate_limited_client) -> None:
        resp = rate_limited_client.post(
            "/v1/activate",
            json={"email": "test@example.com"},
            headers={"Authorization": "Bearer change-me-in-production"},
        )
        assert resp.status_code == 200

    def test_activate_exceeds_limit(self, rate_limited_client) -> None:
        """11th request within a minute should get 429."""
        for i in range(10):
            resp = rate_limited_client.post(
                "/v1/activate",
                json={"email": f"flood{i}@example.com"},
                headers={"Authorization": "Bearer change-me-in-production"},
            )
            assert resp.status_code == 200, f"Request {i + 1} failed: {resp.json()}"

        resp = rate_limited_client.post(
            "/v1/activate",
            json={"email": "flood-extra@example.com"},
            headers={"Authorization": "Bearer change-me-in-production"},
        )
        assert resp.status_code == 429


class TestValidateRateLimit:
    """POST /v1/validate — 60/minute."""

    def test_validate_under_limit(self, rate_limited_client) -> None:
        resp = rate_limited_client.post(
            "/v1/validate",
            json={"license_key": "ANMD-AAAA-BBBB-CCCC"},
        )
        assert resp.status_code == 200


class TestHealthRateLimit:
    """GET /v1/health — 120/minute."""

    def test_health_under_limit(self, rate_limited_client) -> None:
        resp = rate_limited_client.get("/v1/health")
        assert resp.status_code == 200


class TestRateLimitDisabled:
    """Verify limiter can be disabled (as in unit test fixtures)."""

    def test_disabled_limiter_no_429(self, rate_limited_client) -> None:
        limiter.enabled = False
        for _ in range(15):
            resp = rate_limited_client.post(
                "/v1/activate",
                json={"email": "bulk@example.com"},
                headers={"Authorization": "Bearer change-me-in-production"},
            )
            assert resp.status_code == 200
