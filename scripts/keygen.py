#!/usr/bin/env python3
"""Generate valid ClaudeMD Forge Pro license keys.

Usage:
    python scripts/keygen.py              # Generate one key
    python scripts/keygen.py --count 5    # Generate five keys
    python scripts/keygen.py --email user@example.com  # Tag with email
"""

import argparse
import secrets
import sys
from pathlib import Path

# Add src/ to path so we can import the canonical salt and checksum function.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from claudemd_forge.licensing import _compute_check_segment  # noqa: E402


def generate_key() -> str:
    """Generate a valid CMDF-XXXX-XXXX-XXXX license key."""
    seg1 = secrets.token_hex(2).upper()
    seg2 = secrets.token_hex(2).upper()
    body = f"{seg1}-{seg2}"
    check = _compute_check_segment(body)
    return f"CMDF-{seg1}-{seg2}-{check}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ClaudeMD Forge license keys")
    parser.add_argument("--count", type=int, default=1, help="Number of keys to generate")
    parser.add_argument("--email", type=str, help="Associate email (for your records)")
    args = parser.parse_args()

    for _ in range(args.count):
        key = generate_key()
        if args.email:
            print(f"{key}  # {args.email}")  # noqa: T201
        else:
            print(key)  # noqa: T201


if __name__ == "__main__":
    main()
