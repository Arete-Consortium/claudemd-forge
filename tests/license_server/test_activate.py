"""Tests for the activate endpoint."""

from __future__ import annotations

from license_server.key_gen import hash_key, validate_key_checksum, validate_key_format


class TestActivateAuth:
    def test_missing_auth_header(self, client) -> None:
        resp = client.post("/v1/activate", json={"email": "t@t.com"})
        assert resp.status_code == 422  # Missing required header

    def test_invalid_token(self, client) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "t@t.com"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403

    def test_non_bearer_scheme(self, client) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "t@t.com"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401


class TestActivateSuccess:
    def test_returns_201_or_200(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_response_contains_key(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert "license_key" in data
        assert data["license_key"].startswith("ANMD-")

    def test_returned_key_is_valid(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key = resp.json()["license_key"]
        assert validate_key_format(key)
        assert validate_key_checksum(key)

    def test_response_shape(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert data["tier"] == "pro"
        assert data["email"] == "user@example.com"
        assert data["active"] is True
        assert "created_at" in data

    def test_custom_tier(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "tier": "free"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.json()["tier"] == "free"


class TestActivateStorage:
    def test_key_stored_as_hash(self, client, admin_token, db) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key = resp.json()["license_key"]
        expected_hash = hash_key(key)

        row = db.execute(
            "SELECT key_hash FROM licenses WHERE key_hash = ?", (expected_hash,)
        ).fetchone()
        assert row is not None

    def test_plaintext_key_not_stored(self, client, admin_token, db) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key = resp.json()["license_key"]

        # Search for plaintext key in any column.
        row = db.execute("SELECT * FROM licenses WHERE license_key_masked = ?", (key,)).fetchone()
        assert row is None  # Full key should NOT be in masked column

    def test_key_is_masked_in_db(self, client, admin_token, db) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key = resp.json()["license_key"]
        key_h = hash_key(key)

        row = db.execute(
            "SELECT license_key_masked FROM licenses WHERE key_hash = ?", (key_h,)
        ).fetchone()
        assert "****" in row["license_key_masked"]

    def test_email_stored(self, client, admin_token, db) -> None:
        client.post(
            "/v1/activate",
            json={"email": "stored@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        row = db.execute(
            "SELECT email FROM licenses WHERE email = ?", ("stored@example.com",)
        ).fetchone()
        assert row is not None

    def test_multiple_keys_unique(self, client, admin_token) -> None:
        keys = set()
        for _ in range(5):
            resp = client.post(
                "/v1/activate",
                json={"email": "multi@example.com"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            keys.add(resp.json()["license_key"])
        assert len(keys) == 5

    def test_health_reflects_new_license(self, client, admin_token) -> None:
        client.post(
            "/v1/activate",
            json={"email": "count@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        health = client.get("/v1/health").json()
        assert health["total_licenses"] >= 1
        assert health["active_licenses"] >= 1
