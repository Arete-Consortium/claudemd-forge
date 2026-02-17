"""Licensing and tier management for ClaudeMD Forge."""

from __future__ import annotations

import hashlib
import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Salt used to derive the check segment of license keys.
_KEY_SALT = "claudemd-forge-v1"

# License key file locations (checked in order).
_LICENSE_LOCATIONS: list[str] = [
    ".claudemd-forge-license",
    "~/.config/claudemd-forge/license",
    "~/.claudemd-forge-license",
]

_ENV_LICENSE_KEY = "CLAUDEMD_FORGE_LICENSE"


class Tier(StrEnum):
    """Product tier levels."""

    FREE = "free"
    PRO = "pro"


class TierConfig(BaseModel):
    """Configuration for a product tier."""

    name: str
    price_label: str
    features: list[str]
    preset_access: list[str] = Field(default_factory=list)


# Tier definitions with feature lists.
TIER_DEFINITIONS: dict[Tier, TierConfig] = {
    Tier.FREE: TierConfig(
        name="Free",
        price_label="Free forever",
        features=[
            "generate",
            "audit",
            "presets",
            "frameworks",
            "community_presets",
        ],
        preset_access=[
            "default",
            "minimal",
            "full",
            "python-fastapi",
            "python-cli",
            "django",
            "react-typescript",
            "nextjs",
            "rust",
            "go",
            "node-express",
        ],
    ),
    Tier.PRO: TierConfig(
        name="Pro",
        price_label="$8/mo or $69/yr",
        features=[
            "generate",
            "audit",
            "presets",
            "frameworks",
            "community_presets",
            "init_interactive",
            "diff",
            "ci_integration",
            "premium_presets",
            "team_templates",
            "priority_updates",
        ],
        preset_access=[
            "default",
            "minimal",
            "full",
            "monorepo",
            "library",
            "python-fastapi",
            "python-cli",
            "django",
            "react-typescript",
            "nextjs",
            "rust",
            "go",
            "node-express",
            "react-native",
            "data-science",
            "devops",
            "mobile",
        ],
    ),
}

# Features that require Pro.
PRO_FEATURES: frozenset[str] = frozenset(
    {
        "init_interactive",
        "diff",
        "ci_integration",
        "premium_presets",
        "team_templates",
        "priority_updates",
    }
)

# Presets that require Pro.
PRO_PRESETS: frozenset[str] = frozenset(
    {
        "monorepo",
        "library",
        "react-native",
        "data-science",
        "devops",
        "mobile",
    }
)


class LicenseInfo(BaseModel):
    """Validated license information."""

    tier: Tier = Tier.FREE
    license_key: str | None = None
    valid: bool = False
    email: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _validate_key_format(key: str) -> bool:
    """Check if a license key matches the expected format.

    Format: CMDF-XXXX-XXXX-XXXX where X is uppercase alphanumeric.
    """
    key = key.strip()
    if not key.startswith("CMDF-"):
        return False
    parts = key.split("-")
    if len(parts) != 4:
        return False
    for part in parts[1:]:
        if len(part) != 4 or not part.isalnum() or not part.isupper():
            return False
    return True


def _compute_check_segment(body: str) -> str:
    """Derive the expected check segment from the key body.

    The body is the two middle segments joined by a hyphen,
    e.g. "ABCD-EFGH" for key "CMDF-ABCD-EFGH-XXXX".
    Returns a 4-character uppercase hex string.
    """
    digest = hashlib.sha256(f"{_KEY_SALT}:{body}".encode()).hexdigest()
    return digest[:4].upper()


def _validate_key_checksum(key: str) -> bool:
    """Verify the key's check segment matches its body.

    The last segment must equal the HMAC-derived value from
    segments 2 and 3. This prevents trivially guessed keys.
    """
    parts = key.strip().split("-")
    if len(parts) != 4:
        return False
    body = f"{parts[1]}-{parts[2]}"
    expected = _compute_check_segment(body)
    return parts[3] == expected


def _find_license_key() -> str | None:
    """Search for a license key in environment and filesystem."""
    # 1. Check environment variable first.
    env_key = os.environ.get(_ENV_LICENSE_KEY)
    if env_key and env_key.strip():
        return env_key.strip()

    # 2. Check filesystem locations.
    for location in _LICENSE_LOCATIONS:
        path = Path(location).expanduser()
        if path.is_file():
            try:
                content = path.read_text().strip()
                if content:
                    return content
            except OSError:
                continue

    return None


def get_license_info() -> LicenseInfo:
    """Detect and validate the current license.

    Checks environment variables and license files for a valid key.
    Returns LicenseInfo with tier set based on key validity.
    """
    key = _find_license_key()

    if key is None:
        logger.debug("No license key found, using free tier")
        return LicenseInfo(tier=Tier.FREE)

    if not _validate_key_format(key):
        logger.warning("Invalid license key format")
        return LicenseInfo(
            tier=Tier.FREE,
            license_key=key,
            valid=False,
        )

    if not _validate_key_checksum(key):
        logger.warning("License key checksum mismatch")
        return LicenseInfo(
            tier=Tier.FREE,
            license_key=key,
            valid=False,
        )

    # Valid format + checksum — activate Pro tier.
    # In production, this would also verify against a license server.
    return LicenseInfo(
        tier=Tier.PRO,
        license_key=key,
        valid=True,
    )


def has_feature(feature: str) -> bool:
    """Check if the current license grants access to a feature."""
    info = get_license_info()
    tier_config = TIER_DEFINITIONS[info.tier]
    return feature in tier_config.features


def has_preset_access(preset_name: str) -> bool:
    """Check if the current license grants access to a preset."""
    info = get_license_info()
    tier_config = TIER_DEFINITIONS[info.tier]
    return preset_name in tier_config.preset_access


def is_known_preset(preset_name: str) -> bool:
    """Check if a preset name exists in any tier's access list."""
    return any(preset_name in config.preset_access for config in TIER_DEFINITIONS.values())


def is_pro() -> bool:
    """Check if the current license is Pro tier."""
    return get_license_info().tier == Tier.PRO


def get_upgrade_message(feature: str) -> str:
    """Return a user-facing upgrade prompt for a gated feature."""
    pro_config = TIER_DEFINITIONS[Tier.PRO]
    return (
        f"'{feature}' requires ClaudeMD Forge Pro ({pro_config.price_label}).\n"
        f"Upgrade at: https://claudemd-forge.dev/pro\n"
        f"Set your key via: export {_ENV_LICENSE_KEY}=CMDF-XXXX-XXXX-XXXX"
    )
