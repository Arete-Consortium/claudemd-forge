#!/usr/bin/env python3
"""Create AI Cards TCG Stripe products, prices, and payment links.

Prerequisites:
    pip install stripe
    export STRIPE_SECRET_KEY=sk_test_...  (or sk_live_...)

Usage:
    python scripts/stripe_setup_aicards.py           # Test mode
    python scripts/stripe_setup_aicards.py --live     # Live mode

Creates one-time $0.50 payment links for each of the 18 expansion sets.
Webhook metadata:
    product = "aicards-pack"
    pack_type = <series key>

The user's Sui address is passed via client_reference_id URL param:
    https://buy.stripe.com/xxx?client_reference_id=0xABC123
"""

import argparse
import os
import sys

try:
    import stripe
except ImportError:
    print("Install stripe: pip install stripe", file=sys.stderr)  # noqa: T201
    sys.exit(1)

SETS = [
    ("jobless", "Jobless.AI"),
    ("doomscroll", "DOOMSCROLL"),
    ("loveexe", "LOVE.EXE"),
    ("warroom", "WAR ROOM"),
    ("skillsvoid", "SKILLS.VOID"),
    ("founderexe", "FOUNDER.EXE"),
    ("deepstateai", "DEEP STATE AI"),
    ("healthcaresys", "HEALTHCARE.SYS"),
    ("parenttrap", "PARENT TRAP"),
    ("climateerr", "CLIMATE.ERR"),
    ("creatornull", "CREATOR.NULL"),
    ("analogrevival", "ANALOG.REVIVAL"),
    ("mergeprotocol", "MERGE.PROTOCOL"),
    ("ubiworld", "UBI.WORLD"),
    ("walledgarden", "WALLED.GARDEN"),
    ("solarpunk", "SOLARPUNK.SYS"),
    ("greyzone", "GREY.ZONE"),
    ("frontiernull", "FRONTIER.NULL"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Stripe for AI Cards TCG packs")
    parser.add_argument("--live", action="store_true", help="Confirm live mode")
    args = parser.parse_args()

    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        print("Set STRIPE_SECRET_KEY environment variable", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    if key.startswith("sk_live_") and not args.live:
        print("Live key detected. Pass --live to confirm.", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    stripe.api_key = key

    # Create parent product for all AI Cards packs
    product = stripe.Product.create(
        name="AI Cards TCG — Expansion Pack",
        description=(
            "One pack of 5 cards from an AI Cards expansion set. "
            "Cards minted as NFTs on Sui blockchain."
        ),
        metadata={"product": "aicards-pack"},
    )
    print(f"Product: {product.id}")  # noqa: T201

    # Single price for all packs — $0.50 one-time
    price = stripe.Price.create(
        product=product.id,
        unit_amount=50,  # $0.50
        currency="usd",
    )
    print(f"Price: {price.id} ($0.50)\n")  # noqa: T201

    # Create one payment link per set
    links = {}
    for series_key, display_name in SETS:
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={
                "product": "aicards-pack",
                "pack_type": series_key,
            },
            # Allow Stripe to collect email for fulfillment
            # client_reference_id is passed as URL param by the frontend
        )
        links[series_key] = link.url
        print(f"  {display_name:20s} ({series_key}): {link.url}")  # noqa: T201

    # Print JS snippet for frontend
    print("\n── Frontend STRIPE_PACK_LINKS ──")  # noqa: T201
    print("const STRIPE_PACK_LINKS = {")  # noqa: T201
    for series_key, _ in SETS:
        print(f"  {series_key}:'{links[series_key]}',")  # noqa: T201
    print("};")  # noqa: T201

    print(  # noqa: T201
        "\nWebhook reads metadata.product='aicards-pack' + metadata.pack_type."
        "\nSui address from session.client_reference_id."
        "\nEnsure webhook is configured at: "
        "https://anmd-license.fly.dev/v1/webhooks/stripe"
    )


if __name__ == "__main__":
    main()
