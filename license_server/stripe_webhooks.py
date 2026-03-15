"""Stripe webhook handlers for automated license fulfillment.

Handles:
- checkout.session.completed → generate + activate license, email key
- customer.subscription.deleted → revoke license (bundle-aware)
- invoice.payment_failed → log warning (grace period handled by Stripe)

Multi-product: Stripe metadata must include "product" (e.g. "anchormd", "agent-lint").
Defaults to "anchormd" for backward compatibility.

Bundles: When metadata.product = "bundle", metadata.bundle_products is a comma-separated
list of products (e.g. "anchormd,agent-lint,promptctl"). A key is generated for
each product and all keys are sent in a single email.
"""

from __future__ import annotations

import json
import logging
import uuid

from license_server.database import get_connection
from license_server.email_delivery import send_bundle_email, send_license_email
from license_server.key_gen import generate_key, hash_key, mask_key, validate_key_checksum

logger = logging.getLogger(__name__)

# Products included in the "bundle" offering
BUNDLE_PRODUCTS = ["anchormd", "agent-lint", "ai-spend", "promptctl", "context-hygiene"]


def _create_license(
    conn,
    product: str,
    tier: str,
    customer_email: str,
    customer_id: str | None,
    subscription_id: str | None,
    event_id: str | None,
    bundle_id: str | None = None,
) -> tuple[str, str, str]:
    """Create a single license record. Returns (key, masked, license_id)."""
    key = generate_key(product)
    if not validate_key_checksum(key, product):
        logger.error("Generated key failed checksum for %s", product)
        raise RuntimeError(f"Key generation failed for {product}")

    key_h = hash_key(key)
    masked = mask_key(key)
    license_id = str(uuid.uuid4())

    conn.execute(
        "INSERT INTO licenses "
        "(id, key_hash, license_key_masked, tier, email, active, product, "
        "stripe_customer_id, stripe_subscription_id, bundle_id, metadata) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)",
        (
            license_id,
            key_h,
            masked,
            tier,
            customer_email,
            product,
            customer_id,
            subscription_id,
            bundle_id,
            json.dumps({"source": "stripe_checkout", "event_id": event_id}),
        ),
    )

    logger.info(
        "License created for %s (product=%s, tier=%s, bundle=%s)",
        customer_email,
        product,
        tier,
        bundle_id,
    )
    return key, masked, license_id


def handle_checkout_completed(event: dict) -> dict:
    """Process checkout.session.completed — create license(s) and email key(s).

    Returns dict with license_key_masked and email on success.
    For bundles, returns list of all created licenses.
    """
    session = event.get("data", {}).get("object", {})
    customer_email = session.get("customer_details", {}).get("email") or session.get(
        "customer_email"
    )
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not customer_email:
        logger.error("checkout.session.completed missing customer email: %s", event.get("id"))
        return {"error": "missing_email", "event_id": event.get("id")}

    # Extract product and tier from metadata
    metadata = session.get("metadata", {})
    product = metadata.get("product", "anchormd")
    tier = metadata.get("tier", "pro")

    conn = get_connection()

    # Bundle handling: generate a key for each product
    if product == "bundle":
        bundle_products_str = metadata.get("bundle_products", "")
        products = [p.strip() for p in bundle_products_str.split(",") if p.strip()]
        if not products:
            products = BUNDLE_PRODUCTS

        bundle_id = str(uuid.uuid4())
        licenses = []

        for prod in products:
            key, masked, _lid = _create_license(
                conn,
                prod,
                tier,
                customer_email,
                customer_id,
                subscription_id,
                event.get("id"),
                bundle_id,
            )
            licenses.append({"product": prod, "key": key, "masked": masked})

        conn.commit()

        # Send single email with all keys
        send_bundle_email(
            customer_email,
            [(lic["product"], lic["key"]) for lic in licenses],
            tier,
            bundle_id,
        )

        return {
            "bundle_id": bundle_id,
            "email": customer_email,
            "tier": tier,
            "licenses": [{"product": lic["product"], "masked": lic["masked"]} for lic in licenses],
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
        }

    # Single product (existing behavior)
    key, masked, _lid = _create_license(
        conn,
        product,
        tier,
        customer_email,
        customer_id,
        subscription_id,
        event.get("id"),
    )
    conn.commit()

    # Email the key (best-effort — don't fail the webhook)
    send_license_email(customer_email, key, tier, product)

    return {
        "license_key_masked": masked,
        "email": customer_email,
        "product": product,
        "tier": tier,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
    }


def handle_subscription_deleted(event: dict) -> dict:
    """Process customer.subscription.deleted — revoke associated license(s).

    Bundle-aware: if the license has a bundle_id, all licenses in the bundle are revoked.
    """
    subscription = event.get("data", {}).get("object", {})
    subscription_id = subscription.get("id")

    if not subscription_id:
        logger.error("subscription.deleted missing subscription id: %s", event.get("id"))
        return {"error": "missing_subscription_id", "event_id": event.get("id")}

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, license_key_masked, email, product, bundle_id FROM licenses "
        "WHERE stripe_subscription_id = ? AND active = 1",
        (subscription_id,),
    ).fetchall()

    if not rows:
        logger.warning("No active license found for subscription %s", subscription_id)
        return {"error": "license_not_found", "subscription_id": subscription_id}

    # Collect all license IDs to revoke (including bundle siblings)
    ids_to_revoke = set()
    bundle_id = None
    for row in rows:
        ids_to_revoke.add(row["id"])
        if row["bundle_id"]:
            bundle_id = row["bundle_id"]

    # If part of a bundle, revoke all sibling licenses too
    if bundle_id:
        siblings = conn.execute(
            "SELECT id FROM licenses WHERE bundle_id = ? AND active = 1",
            (bundle_id,),
        ).fetchall()
        for sib in siblings:
            ids_to_revoke.add(sib["id"])

    for lid in ids_to_revoke:
        conn.execute("UPDATE licenses SET active = 0 WHERE id = ?", (lid,))
        conn.execute(
            "INSERT INTO validation_log (key_hash, machine_id, result, ip_address) "
            "SELECT key_hash, NULL, 'revoked_subscription_cancelled', 'stripe_webhook' "
            "FROM licenses WHERE id = ?",
            (lid,),
        )

    conn.commit()

    email = rows[0]["email"]
    revoked_products = [r["product"] for r in rows]
    logger.info(
        "License(s) revoked for %s (products=%s, bundle=%s, sub=%s cancelled)",
        email,
        revoked_products,
        bundle_id,
        subscription_id,
    )

    return {
        "revoked": True,
        "revoked_count": len(ids_to_revoke),
        "bundle_id": bundle_id,
        "email": email,
        "products": revoked_products,
        "subscription_id": subscription_id,
    }


def handle_payment_failed(event: dict) -> dict:
    """Process invoice.payment_failed — log warning.

    Stripe handles retry logic and dunning emails.
    We log it for visibility but don't revoke — Stripe will send
    customer.subscription.deleted if all retries fail.
    """
    invoice = event.get("data", {}).get("object", {})
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email")

    logger.warning(
        "Payment failed for %s (sub=%s). Stripe will retry.",
        customer_email,
        subscription_id,
    )

    return {
        "logged": True,
        "email": customer_email,
        "subscription_id": subscription_id,
    }


# Map event types to handlers
EVENT_HANDLERS: dict[str, object] = {
    "checkout.session.completed": handle_checkout_completed,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_failed": handle_payment_failed,
}
