"""License key generation and hashing utilities.

Multi-product: generates keys with product-specific prefixes and salts.
Each product's checksum algorithm matches its client-side licensing.py.
"""

from __future__ import annotations

import hashlib
import secrets

# Product → (prefix, salt) mapping
# Must match the client-side _PREFIX and _SALT in each product's licensing.py
PRODUCT_KEY_CONFIG: dict[str, tuple[str, str]] = {
    "anchormd": ("ANMD", "anchormd-v1"),
    "agent-lint": ("ALNT", "agent-lint-v1"),
    "ai-spend": ("ASPD", "ai-spend-v1"),
    "promptctl": ("PCTL", "promptctl-v1"),
    "context-hygiene": ("CTHG", "context-hygiene-v1"),
}

_DEFAULT_PRODUCT = "anchormd"


def _compute_check_segment(body: str, salt: str) -> str:
    """Derive the check segment from the two middle key segments.

    Algorithm: SHA256(salt:body)[:4].upper()
    Identical to each product's client-side implementation.
    """
    digest = hashlib.sha256(f"{salt}:{body}".encode()).hexdigest()
    return digest[:4].upper()


def generate_key(product: str = _DEFAULT_PRODUCT) -> str:
    """Generate a valid license key for the given product.

    Format: PREFIX-XXXX-XXXX-XXXX (e.g. ANMD-A1B2-C3D4-54EF)
    Returns the full plaintext key (only exposed once at activation time).
    """
    config = PRODUCT_KEY_CONFIG.get(product)
    if config is None:
        raise ValueError(f"Unknown product: {product!r}. Known: {list(PRODUCT_KEY_CONFIG)}")

    prefix, salt = config
    seg1 = secrets.token_hex(2).upper()
    seg2 = secrets.token_hex(2).upper()
    body = f"{seg1}-{seg2}"
    check = _compute_check_segment(body, salt)
    return f"{prefix}-{seg1}-{seg2}-{check}"


def hash_key(key: str) -> str:
    """Return the SHA-256 hex digest of a plaintext license key.

    Used for database lookups — the plaintext key is never stored.
    """
    return hashlib.sha256(key.strip().encode()).hexdigest()


def mask_key(key: str) -> str:
    """Return a masked version of the key for display/storage.

    ANMD-ABCD-EFGH-54EF -> ANMD-****-****-54EF
    ALNT-ABCD-EFGH-54EF -> ALNT-****-****-54EF
    """
    parts = key.strip().split("-")
    if len(parts) != 4:
        return "****-****-****-****"
    return f"{parts[0]}-****-****-{parts[3]}"


def validate_key_format(key: str, product: str = _DEFAULT_PRODUCT) -> bool:
    """Check if a key matches PREFIX-XXXX-XXXX-XXXX format for the given product."""
    config = PRODUCT_KEY_CONFIG.get(product)
    if config is None:
        return False

    prefix = config[0]
    key = key.strip()
    if not key.startswith(f"{prefix}-"):
        return False
    parts = key.split("-")
    if len(parts) != 4:
        return False
    for part in parts[1:]:
        if len(part) != 4 or not part.isalnum() or part != part.upper():
            return False
    return True


def validate_key_checksum(key: str, product: str = _DEFAULT_PRODUCT) -> bool:
    """Verify the key's check segment matches its body for the given product."""
    config = PRODUCT_KEY_CONFIG.get(product)
    if config is None:
        return False

    _, salt = config
    parts = key.strip().split("-")
    if len(parts) != 4:
        return False
    body = f"{parts[1]}-{parts[2]}"
    expected = _compute_check_segment(body, salt)
    return parts[3] == expected
