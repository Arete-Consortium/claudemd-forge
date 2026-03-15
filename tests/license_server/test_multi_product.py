"""Tests for multi-product license support."""

from __future__ import annotations

from license_server.key_gen import hash_key


class TestMultiProductActivate:
    """Activate licenses for different products."""

    def test_activate_default_product(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["product"] == "anchormd"

    def test_activate_agent_lint(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "product": "agent-lint"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["product"] == "agent-lint"

    def test_activate_unknown_product_rejected(self, client, admin_token) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "product": "fake-product"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "Unknown product" in resp.json()["detail"]

    def test_activate_all_valid_products(self, client, admin_token) -> None:
        for product in ("anchormd", "agent-lint", "ai-spend", "promptctl"):
            resp = client.post(
                "/v1/activate",
                json={"email": "user@example.com", "product": product},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["product"] == product

    def test_product_stored_in_db(self, client, admin_token, db) -> None:
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "product": "agent-lint"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key = resp.json()["license_key"]
        key_h = hash_key(key)

        row = db.execute("SELECT product FROM licenses WHERE key_hash = ?", (key_h,)).fetchone()
        assert row["product"] == "agent-lint"


class TestMultiProductValidate:
    """Validate keys are scoped to their product."""

    def _activate(self, client, admin_token, product="anchormd"):
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "product": product},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return resp.json()["license_key"]

    def test_validate_correct_product(self, client, admin_token) -> None:
        key = self._activate(client, admin_token, "agent-lint")
        resp = client.post(
            "/v1/validate",
            json={"license_key": key, "product": "agent-lint"},
        )
        assert resp.json()["valid"] is True
        assert resp.json()["product"] == "agent-lint"

    def test_validate_wrong_product_fails(self, client, admin_token) -> None:
        key = self._activate(client, admin_token, "agent-lint")
        resp = client.post(
            "/v1/validate",
            json={"license_key": key, "product": "anchormd"},
        )
        assert resp.json()["valid"] is False

    def test_same_key_different_products_isolated(self, client, admin_token) -> None:
        """Keys for one product don't validate against another."""
        key_forge = self._activate(client, admin_token, "anchormd")
        key_lint = self._activate(client, admin_token, "agent-lint")

        # Each validates only for its own product
        assert (
            client.post(
                "/v1/validate",
                json={"license_key": key_forge, "product": "anchormd"},
            ).json()["valid"]
            is True
        )

        assert (
            client.post(
                "/v1/validate",
                json={"license_key": key_forge, "product": "agent-lint"},
            ).json()["valid"]
            is False
        )

        assert (
            client.post(
                "/v1/validate",
                json={"license_key": key_lint, "product": "agent-lint"},
            ).json()["valid"]
            is True
        )

        assert (
            client.post(
                "/v1/validate",
                json={"license_key": key_lint, "product": "anchormd"},
            ).json()["valid"]
            is False
        )

    def test_default_product_backward_compat(self, client, admin_token) -> None:
        """Omitting product defaults to anchormd."""
        key = self._activate(client, admin_token, "anchormd")
        resp = client.post(
            "/v1/validate",
            json={"license_key": key},
        )
        assert resp.json()["valid"] is True
        assert resp.json()["product"] == "anchormd"


class TestMultiProductRevoke:
    """Revoke is scoped to product."""

    def _activate(self, client, admin_token, product="anchormd"):
        resp = client.post(
            "/v1/activate",
            json={"email": "user@example.com", "product": product},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return resp.json()["license_key"]

    def test_revoke_correct_product(self, client, admin_token) -> None:
        key = self._activate(client, admin_token, "agent-lint")
        resp = client.post(
            "/v1/revoke",
            json={"license_key": key, "product": "agent-lint"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True
        assert resp.json()["product"] == "agent-lint"

    def test_revoke_wrong_product_404(self, client, admin_token) -> None:
        key = self._activate(client, admin_token, "agent-lint")
        resp = client.post(
            "/v1/revoke",
            json={"license_key": key, "product": "anchormd"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
