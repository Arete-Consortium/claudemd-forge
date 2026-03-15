"""Tests for the validate endpoint."""

from __future__ import annotations

import json
import uuid

from license_server.key_gen import generate_key, hash_key


def _activate_key(db, *, active=1, tier="pro", email="t@t.com", expires_at=None, metadata=None):
    """Insert a license directly into the DB. Returns the plaintext key."""
    key = generate_key()
    key_h = hash_key(key)
    db.execute(
        "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email, active, "
        "expires_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            key_h,
            f"ANMD-****-****-{key.split('-')[3]}",
            tier,
            email,
            active,
            expires_at,
            json.dumps(metadata or {}),
        ),
    )
    db.commit()
    return key


class TestValidateValid:
    def test_valid_key_returns_true(self, client, db) -> None:
        key = _activate_key(db)
        resp = client.post("/v1/validate", json={"license_key": key})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_valid_key_returns_tier(self, client, db) -> None:
        key = _activate_key(db, tier="pro")
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["tier"] == "pro"

    def test_valid_key_returns_email(self, client, db) -> None:
        key = _activate_key(db, email="user@example.com")
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["email"] == "user@example.com"

    def test_valid_key_returns_active(self, client, db) -> None:
        key = _activate_key(db)
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["active"] is True

    def test_valid_key_returns_metadata(self, client, db) -> None:
        key = _activate_key(db, metadata={"org": "acme"})
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["metadata"]["org"] == "acme"


class TestValidateInvalid:
    def test_bad_format(self, client) -> None:
        resp = client.post("/v1/validate", json={"license_key": "not-a-key"})
        assert resp.json()["valid"] is False
        assert resp.json()["tier"] == "free"

    def test_bad_checksum(self, client) -> None:
        resp = client.post("/v1/validate", json={"license_key": "ANMD-ABCD-EFGH-XXXX"})
        assert resp.json()["valid"] is False

    def test_valid_format_not_in_db(self, client) -> None:
        key = generate_key()  # Not stored in DB
        resp = client.post("/v1/validate", json={"license_key": key})
        assert resp.json()["valid"] is False

    def test_empty_key(self, client) -> None:
        resp = client.post("/v1/validate", json={"license_key": ""})
        assert resp.json()["valid"] is False


class TestValidateRevoked:
    def test_revoked_key(self, client, db) -> None:
        key = _activate_key(db, active=0)
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["valid"] is False
        assert data["active"] is False


class TestValidateExpired:
    def test_expired_key(self, client, db) -> None:
        key = _activate_key(db, expires_at="2020-01-01T00:00:00")
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["valid"] is False

    def test_future_expiry_still_valid(self, client, db) -> None:
        key = _activate_key(db, expires_at="2099-12-31T23:59:59")
        data = client.post("/v1/validate", json={"license_key": key}).json()
        assert data["valid"] is True


class TestMachineTracking:
    def test_machine_id_recorded(self, client, db) -> None:
        key = _activate_key(db)
        client.post(
            "/v1/validate",
            json={"license_key": key, "machine_id": "machine-abc"},
        )
        row = db.execute(
            "SELECT * FROM machine_activations WHERE machine_id = ?", ("machine-abc",)
        ).fetchone()
        assert row is not None

    def test_multiple_machines_recorded(self, client, db) -> None:
        key = _activate_key(db)
        client.post("/v1/validate", json={"license_key": key, "machine_id": "m1"})
        client.post("/v1/validate", json={"license_key": key, "machine_id": "m2"})
        rows = db.execute("SELECT * FROM machine_activations").fetchall()
        assert len(rows) == 2

    def test_same_machine_updates_last_seen(self, client, db) -> None:
        key = _activate_key(db)
        client.post("/v1/validate", json={"license_key": key, "machine_id": "m1"})
        client.post("/v1/validate", json={"license_key": key, "machine_id": "m1"})
        rows = db.execute(
            "SELECT * FROM machine_activations WHERE machine_id = ?", ("m1",)
        ).fetchall()
        assert len(rows) == 1  # No duplicate

    def test_no_machine_id_no_tracking(self, client, db) -> None:
        key = _activate_key(db)
        client.post("/v1/validate", json={"license_key": key})
        rows = db.execute("SELECT * FROM machine_activations").fetchall()
        assert len(rows) == 0


class TestValidationLog:
    def test_valid_key_logged(self, client, db) -> None:
        key = _activate_key(db)
        client.post("/v1/validate", json={"license_key": key})
        row = db.execute("SELECT result FROM validation_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["result"] == "valid"

    def test_invalid_key_logged(self, client, db) -> None:
        client.post("/v1/validate", json={"license_key": "garbage"})
        row = db.execute("SELECT result FROM validation_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["result"] == "invalid_format"

    def test_not_found_logged(self, client, db) -> None:
        key = generate_key()
        client.post("/v1/validate", json={"license_key": key})
        row = db.execute("SELECT result FROM validation_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["result"] == "not_found"

    def test_revoked_logged(self, client, db) -> None:
        key = _activate_key(db, active=0)
        client.post("/v1/validate", json={"license_key": key})
        row = db.execute("SELECT result FROM validation_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["result"] == "revoked"
