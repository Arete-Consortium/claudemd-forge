"""Tests for usage tracking — scan counter + quota enforcement."""

from __future__ import annotations

from license_server.key_gen import generate_key, hash_key


def _create_license(db, product="anchormd", tier="pro"):
    """Insert a test license and return the key."""
    key = generate_key(product)
    key_h = hash_key(key)
    db.execute(
        "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email, active, product) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (f"lic-{key_h[:8]}", key_h, f"ANMD-****-****-{key[-4:]}", tier, "test@test.com", product),
    )
    db.commit()
    return key


class TestUsageCheck:
    """POST /v1/usage/check — quota inquiry."""

    def test_pro_has_10_deep_scans(self, client, db):

        key = _create_license(db, tier="pro")
        resp = client.post(
            "/v1/usage/check",
            json={
                "license_key": key,
                "scan_type": "deep_scan",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 10
        assert body["used"] == 0
        assert body["remaining"] == 10
        assert body["allowed"] is True

    def test_pro_unlimited_audits(self, client, db):

        key = _create_license(db, tier="pro")
        resp = client.post(
            "/v1/usage/check",
            json={
                "license_key": key,
                "scan_type": "audit",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == -1  # unlimited
        assert body["allowed"] is True

    def test_invalid_key_gets_free_tier(self, client):

        resp = client.post(
            "/v1/usage/check",
            json={
                "license_key": "INVALID-KEY",
                "scan_type": "deep_scan",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 0
        assert body["allowed"] is False

    def test_free_tier_allows_1_audit(self, client):

        resp = client.post(
            "/v1/usage/check",
            json={
                "license_key": "INVALID-KEY",
                "scan_type": "audit",
            },
        )
        body = resp.json()
        assert body["limit"] == 1
        assert body["allowed"] is True


class TestUsageRecord:
    """POST /v1/usage — record a scan and check updated quota."""

    def test_record_deep_scan(self, client, db):

        key = _create_license(db, tier="pro")
        resp = client.post(
            "/v1/usage",
            json={
                "license_key": key,
                "scan_type": "deep_scan",
                "repo_fingerprint": "abc123",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["used"] == 1
        assert body["remaining"] == 9
        assert body["allowed"] is True

    def test_deep_scan_quota_exhaustion(self, client, db):

        key = _create_license(db, tier="pro")

        # Use all 10 scans
        for i in range(10):
            resp = client.post(
                "/v1/usage",
                json={
                    "license_key": key,
                    "scan_type": "deep_scan",
                    "repo_fingerprint": f"repo-{i}",
                },
            )
            assert resp.json()["allowed"] is True

        # 11th should be denied
        resp = client.post(
            "/v1/usage",
            json={
                "license_key": key,
                "scan_type": "deep_scan",
                "repo_fingerprint": "repo-11",
            },
        )
        body = resp.json()
        assert body["used"] == 10
        assert body["remaining"] == 0
        assert body["allowed"] is False

    def test_free_tier_no_deep_scans(self, client, db):

        key = _create_license(db, tier="free")
        resp = client.post(
            "/v1/usage",
            json={
                "license_key": key,
                "scan_type": "deep_scan",
            },
        )
        body = resp.json()
        assert body["allowed"] is False
        assert body["limit"] == 0

    def test_pro_unlimited_audits_record(self, client, db):

        key = _create_license(db, tier="pro")

        # Record many audits — should never be denied
        for i in range(20):
            resp = client.post(
                "/v1/usage",
                json={
                    "license_key": key,
                    "scan_type": "audit",
                    "repo_fingerprint": f"repo-{i}",
                },
            )
            assert resp.json()["allowed"] is True

    def test_usage_has_period(self, client, db):

        key = _create_license(db, tier="pro")
        resp = client.post(
            "/v1/usage",
            json={
                "license_key": key,
                "scan_type": "deep_scan",
            },
        )
        body = resp.json()
        assert len(body["period"]) == 7  # YYYY-MM format
        assert "-" in body["period"]
