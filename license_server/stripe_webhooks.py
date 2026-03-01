"""Stripe webhook handlers — Phase 2 stub.

Will handle:
- checkout.session.completed → activate license
- customer.subscription.deleted → revoke license
- invoice.payment_failed → grace period logic
"""

from __future__ import annotations


def handle_webhook(payload: bytes, signature: str) -> dict:
    """Process a Stripe webhook event. Not yet implemented."""
    raise NotImplementedError("Stripe webhooks are a Phase 2 feature")
