#!/usr/bin/env python3
"""Create AnchorMD products and prices on Stripe.

Prerequisites:
    pip install stripe
    export STRIPE_SECRET_KEY=sk_test_...  (or sk_live_...)

Usage:
    python scripts/stripe_setup.py           # Creates product + both prices
    python scripts/stripe_setup.py --live    # Confirm live mode

This creates:
    - Product: "AnchorMD Pro"
    - Price: $8/month (recurring)
    - Price: $69/year (recurring)
    - Payment Links for both (printed to stdout)
"""

import argparse
import os
import sys

try:
    import stripe
except ImportError:
    print("Install stripe: pip install stripe", file=sys.stderr)  # noqa: T201
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Stripe for AnchorMD Pro")
    parser.add_argument("--live", action="store_true", help="Confirm live mode (not test)")
    args = parser.parse_args()

    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        print("Set STRIPE_SECRET_KEY environment variable", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    if key.startswith("sk_live_") and not args.live:
        print(  # noqa: T201
            "Live key detected. Pass --live to confirm.",
            file=sys.stderr,
        )
        sys.exit(1)

    stripe.api_key = key

    # Create product
    product = stripe.Product.create(
        name="AnchorMD Pro",
        description=(
            "Premium features for AnchorMD: interactive setup, drift detection, "
            "premium presets, team templates, and priority support."
        ),
        metadata={"app": "anchormd", "tier": "pro"},
    )
    print(f"Product: {product.id}")  # noqa: T201

    # Monthly price
    monthly = stripe.Price.create(
        product=product.id,
        unit_amount=800,  # $8.00
        currency="usd",
        recurring={"interval": "month"},
        metadata={"plan": "monthly"},
    )
    print(f"Monthly price: {monthly.id} ($8/mo)")  # noqa: T201

    # Yearly price
    yearly = stripe.Price.create(
        product=product.id,
        unit_amount=6900,  # $69.00
        currency="usd",
        recurring={"interval": "year"},
        metadata={"plan": "yearly"},
    )
    print(f"Yearly price: {yearly.id} ($69/yr)")  # noqa: T201

    # Create payment links
    monthly_link = stripe.PaymentLink.create(
        line_items=[{"price": monthly.id, "quantity": 1}],
        after_completion={"type": "redirect", "redirect": {"url": "https://arete-consortium.github.io/anchormd/?purchased=true"}},
        metadata={"app": "anchormd", "plan": "monthly"},
    )
    print(f"\nMonthly payment link: {monthly_link.url}")  # noqa: T201

    yearly_link = stripe.PaymentLink.create(
        line_items=[{"price": yearly.id, "quantity": 1}],
        after_completion={"type": "redirect", "redirect": {"url": "https://arete-consortium.github.io/anchormd/?purchased=true"}},
        metadata={"app": "anchormd", "plan": "yearly"},
    )
    print(f"Yearly payment link: {yearly_link.url}")  # noqa: T201

    print(  # noqa: T201
        "\nDone. Add these payment links to your landing page."
        "\nFor fulfillment: when you get a Stripe payment notification,"
        "\nrun `python scripts/keygen.py --email <customer>` and send the key."
    )


if __name__ == "__main__":
    main()
