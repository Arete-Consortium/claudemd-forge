"""Tests for the health endpoint."""

from __future__ import annotations

from license_server import __version__


class TestHealthEndpoint:
    def test_health_returns_200(self, client) -> None:
        resp = client.get("/v1/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client) -> None:
        data = client.get("/v1/health").json()
        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert "total_licenses" in data
        assert "active_licenses" in data

    def test_health_initial_counts_zero(self, client) -> None:
        data = client.get("/v1/health").json()
        assert data["total_licenses"] == 0
        assert data["active_licenses"] == 0

    def test_health_version_matches_package(self, client) -> None:
        data = client.get("/v1/health").json()
        assert data["version"] == "0.1.0"

    def test_health_counts_after_insert(self, client, db) -> None:
        import hashlib
        import uuid

        key_hash = hashlib.sha256(b"test-key").hexdigest()
        db.execute(
            "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email, active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), key_hash, "ANMD-****-****-XXXX", "pro", "test@test.com", 1),
        )
        db.commit()

        data = client.get("/v1/health").json()
        assert data["total_licenses"] == 1
        assert data["active_licenses"] == 1

    def test_health_inactive_not_counted_as_active(self, client, db) -> None:
        import hashlib
        import uuid

        key_hash = hashlib.sha256(b"inactive-key").hexdigest()
        db.execute(
            "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email, active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), key_hash, "ANMD-****-****-XXXX", "pro", "test@test.com", 0),
        )
        db.commit()

        data = client.get("/v1/health").json()
        assert data["total_licenses"] == 1
        assert data["active_licenses"] == 0
