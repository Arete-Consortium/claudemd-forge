"""Tests for the revoke endpoint."""

from __future__ import annotations

import json
import uuid

from license_server.key_gen import generate_key, hash_key


def _activate_key(db, *, active=1, tier="pro", email="t@t.com"):
    """Insert a license directly into the DB. Returns the plaintext key."""
    key = generate_key()
    key_h = hash_key(key)
    masked = f"CMDF-****-****-{key.split('-')[3]}"
    db.execute(
        "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email, active, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), key_h, masked, tier, email, active, json.dumps({})),
    )
    db.commit()
    return key


class TestRevokeAuth:
    def test_missing_auth_header(self, client) -> None:
        resp = client.post("/v1/revoke", json={"license_key": "x"})
        assert resp.status_code == 422

    def test_invalid_token(self, client) -> None:
        resp = client.post(
            "/v1/revoke",
            json={"license_key": "x"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403

    def test_non_bearer_scheme(self, client) -> None:
        resp = client.post(
            "/v1/revoke",
            json={"license_key": "x"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401


class TestRevokeSuccess:
    def test_revoke_active_key(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        resp = client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked"] is True
        assert "****" in data["license_key_masked"]
        assert "revoked_at" in data

    def test_revoke_returns_email(self, client, db, admin_token) -> None:
        key = _activate_key(db, email="revoke@example.com")
        data = client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        assert data["email"] == "revoke@example.com"

    def test_db_active_set_to_zero(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        row = db.execute(
            "SELECT active FROM licenses WHERE key_hash = ?", (hash_key(key),)
        ).fetchone()
        assert row["active"] == 0


class TestRevokeIdempotent:
    def test_revoke_already_revoked_key(self, client, db, admin_token) -> None:
        key = _activate_key(db, active=0)
        resp = client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True

    def test_double_revoke(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        for _ in range(2):
            resp = client.post(
                "/v1/revoke",
                json={"license_key": key},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 200


class TestRevokeNotFound:
    def test_unknown_key_returns_404(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/revoke",
            json={"license_key": "CMDF-FAKE-FAKE-FAKE"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


class TestRevokeValidateIntegration:
    def test_validate_after_revoke(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        # Confirm valid first.
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["valid"] is True

        # Revoke.
        client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Now invalid.
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["valid"] is False
        assert data["active"] is False


class TestRevokeAuditLog:
    def test_revocation_logged(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        row = db.execute("SELECT result FROM validation_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["result"] == "revoked_by_admin"

    def test_revocation_log_has_key_hash(self, client, db, admin_token) -> None:
        key = _activate_key(db)
        client.post(
            "/v1/revoke",
            json={"license_key": key},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key_h = hash_key(key)
        row = db.execute(
            "SELECT key_hash FROM validation_log WHERE result = 'revoked_by_admin'"
        ).fetchone()
        assert row["key_hash"] == key_h
