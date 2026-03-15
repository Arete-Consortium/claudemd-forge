"""Tests for Stripe webhook handlers (business logic, no Stripe SDK needed)."""

from __future__ import annotations

import json
import sqlite3

import pytest

from license_server.database import run_migrations
from license_server.stripe_webhooks import (
    handle_checkout_completed,
    handle_payment_failed,
    handle_subscription_deleted,
)


@pytest.fixture
def db():
    """In-memory SQLite database with migrations applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn)
    return conn


@pytest.fixture(autouse=True)
def _patch_db(db, monkeypatch):
    """Patch get_connection to return the test DB."""
    monkeypatch.setattr("license_server.stripe_webhooks.get_connection", lambda *a, **kw: db)


@pytest.fixture(autouse=True)
def _patch_email(monkeypatch):
    """Stub out email delivery."""
    monkeypatch.setattr("license_server.stripe_webhooks.send_license_email", lambda *a, **kw: True)
    monkeypatch.setattr("license_server.stripe_webhooks.send_bundle_email", lambda *a, **kw: True)


def _checkout_event(
    email: str = "buyer@example.com",
    customer_id: str = "cus_test123",
    subscription_id: str = "sub_test456",
    tier: str = "pro",
    event_id: str = "evt_test789",
) -> dict:
    """Build a minimal checkout.session.completed event."""
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_details": {"email": email},
                "customer": customer_id,
                "subscription": subscription_id,
                "metadata": {"tier": tier},
            }
        },
    }


def _subscription_deleted_event(
    subscription_id: str = "sub_test456",
    event_id: str = "evt_cancel",
) -> dict:
    """Build a minimal customer.subscription.deleted event."""
    return {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": subscription_id,
            }
        },
    }


def _payment_failed_event(
    subscription_id: str = "sub_test456",
    email: str = "buyer@example.com",
) -> dict:
    return {
        "id": "evt_fail",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": subscription_id,
                "customer_email": email,
            }
        },
    }


class TestCheckoutCompleted:
    """Tests for checkout.session.completed handler."""

    def test_creates_license(self, db):
        result = handle_checkout_completed(_checkout_event())

        assert "license_key_masked" in result
        assert result["email"] == "buyer@example.com"
        assert result["tier"] == "pro"
        assert result["stripe_customer_id"] == "cus_test123"
        assert result["stripe_subscription_id"] == "sub_test456"

        # Verify DB row
        row = db.execute(
            "SELECT * FROM licenses WHERE email = ?", ("buyer@example.com",)
        ).fetchone()
        assert row is not None
        assert row["active"] == 1
        assert row["tier"] == "pro"
        assert row["stripe_customer_id"] == "cus_test123"
        assert row["stripe_subscription_id"] == "sub_test456"

    def test_key_is_valid(self, db):
        result = handle_checkout_completed(_checkout_event())

        masked = result["license_key_masked"]
        assert masked.startswith("ANMD-****-****-")
        assert len(masked) == 19

    def test_missing_email_returns_error(self, db):
        event = _checkout_event()
        event["data"]["object"]["customer_details"]["email"] = None
        event["data"]["object"].pop("customer_email", None)

        result = handle_checkout_completed(event)
        assert result["error"] == "missing_email"

    def test_customer_email_fallback(self, db):
        """Falls back to customer_email if customer_details.email is missing."""
        event = _checkout_event()
        event["data"]["object"]["customer_details"]["email"] = None
        event["data"]["object"]["customer_email"] = "fallback@example.com"

        result = handle_checkout_completed(event)
        assert result["email"] == "fallback@example.com"

    def test_default_tier_is_pro(self, db):
        event = _checkout_event()
        event["data"]["object"]["metadata"] = {}

        result = handle_checkout_completed(event)
        assert result["tier"] == "pro"

    def test_stores_event_metadata(self, db):
        handle_checkout_completed(_checkout_event(event_id="evt_abc"))

        row = db.execute(
            "SELECT metadata FROM licenses WHERE email = ?",
            ("buyer@example.com",),
        ).fetchone()
        meta = json.loads(row["metadata"])
        assert meta["source"] == "stripe_checkout"
        assert meta["event_id"] == "evt_abc"

    def test_multiple_purchases_create_separate_licenses(self, db):
        handle_checkout_completed(_checkout_event(subscription_id="sub_1"))
        handle_checkout_completed(_checkout_event(subscription_id="sub_2"))

        count = db.execute(
            "SELECT COUNT(*) FROM licenses WHERE email = ?",
            ("buyer@example.com",),
        ).fetchone()[0]
        assert count == 2


class TestSubscriptionDeleted:
    """Tests for customer.subscription.deleted handler."""

    def test_revokes_license(self, db):
        handle_checkout_completed(_checkout_event())

        result = handle_subscription_deleted(_subscription_deleted_event())

        assert result["revoked"] is True
        assert result["email"] == "buyer@example.com"
        assert result["subscription_id"] == "sub_test456"

        row = db.execute(
            "SELECT active FROM licenses WHERE stripe_subscription_id = ?",
            ("sub_test456",),
        ).fetchone()
        assert row["active"] == 0

    def test_logs_revocation_audit(self, db):
        handle_checkout_completed(_checkout_event())
        handle_subscription_deleted(_subscription_deleted_event())

        log = db.execute(
            "SELECT result FROM validation_log WHERE result = 'revoked_subscription_cancelled'"
        ).fetchone()
        assert log is not None

    def test_missing_subscription_returns_error(self, db):
        result = handle_subscription_deleted(
            _subscription_deleted_event(subscription_id="sub_nonexistent")
        )
        assert result["error"] == "license_not_found"

    def test_already_revoked_returns_not_found(self, db):
        handle_checkout_completed(_checkout_event())
        handle_subscription_deleted(_subscription_deleted_event())

        result = handle_subscription_deleted(_subscription_deleted_event())
        assert result["error"] == "license_not_found"

    def test_missing_subscription_id_field(self, db):
        event = {
            "id": "evt_bad",
            "type": "customer.subscription.deleted",
            "data": {"object": {}},
        }
        result = handle_subscription_deleted(event)
        assert result["error"] == "missing_subscription_id"


class TestPaymentFailed:
    """Tests for invoice.payment_failed handler."""

    def test_logs_warning(self, db):
        result = handle_payment_failed(_payment_failed_event())

        assert result["logged"] is True
        assert result["email"] == "buyer@example.com"
        assert result["subscription_id"] == "sub_test456"

    def test_does_not_revoke(self, db):
        handle_checkout_completed(_checkout_event())
        handle_payment_failed(_payment_failed_event())

        row = db.execute(
            "SELECT active FROM licenses WHERE stripe_subscription_id = ?",
            ("sub_test456",),
        ).fetchone()
        assert row["active"] == 1


# ---------------------------------------------------------------------------
# Bundle tests
# ---------------------------------------------------------------------------


def _bundle_checkout_event(
    products: str = "anchormd,agent-lint,promptctl",
    subscription_id: str = "sub_bundle_789",
    event_id: str = "evt_bundle_001",
) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_details": {"email": "bundle@example.com"},
                "customer": "cus_bundle",
                "subscription": subscription_id,
                "metadata": {
                    "product": "bundle",
                    "bundle_products": products,
                    "tier": "pro",
                },
            }
        },
    }


class TestBundleCheckout:
    """Tests for bundle checkout handling."""

    def test_creates_multiple_licenses(self, db):
        result = handle_checkout_completed(_bundle_checkout_event())
        assert "bundle_id" in result
        assert len(result["licenses"]) == 3

        count = db.execute(
            "SELECT COUNT(*) FROM licenses WHERE email = ?",
            ("bundle@example.com",),
        ).fetchone()[0]
        assert count == 3

    def test_all_products_have_correct_prefix(self, db):
        result = handle_checkout_completed(_bundle_checkout_event())
        prefixes = {lic["masked"][:4] for lic in result["licenses"]}
        assert prefixes == {"ANMD", "ALNT", "PCTL"}

    def test_all_licenses_share_bundle_id(self, db):
        result = handle_checkout_completed(_bundle_checkout_event())
        bundle_id = result["bundle_id"]

        rows = db.execute(
            "SELECT bundle_id FROM licenses WHERE email = ?",
            ("bundle@example.com",),
        ).fetchall()
        assert all(row["bundle_id"] == bundle_id for row in rows)

    def test_default_bundle_products_when_empty(self, db):
        result = handle_checkout_completed(_bundle_checkout_event(products=""))
        # Should fall back to BUNDLE_PRODUCTS (all 5)
        assert len(result["licenses"]) == 5

    def test_bundle_revocation_revokes_all(self, db):
        handle_checkout_completed(_bundle_checkout_event(subscription_id="sub_bundle_rev"))

        result = handle_subscription_deleted(
            _subscription_deleted_event(subscription_id="sub_bundle_rev")
        )

        assert result["revoked"] is True
        assert result["revoked_count"] == 3

        active = db.execute(
            "SELECT COUNT(*) FROM licenses WHERE email = ? AND active = 1",
            ("bundle@example.com",),
        ).fetchone()[0]
        assert active == 0
