"""Licensing and tier management for AnchorMD."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Salt used to derive the check segment of license keys.
_KEY_SALT = "anchormd-v1"
_LEGACY_KEY_SALT = "claudemd-forge-v1"

# License key file locations (checked in order).
_LICENSE_LOCATIONS: list[str] = [
    ".anchormd-license",
    "~/.config/anchormd/license",
    "~/.anchormd-license",
    # Legacy paths for backward compatibility
    ".claudemd-forge-license",
    "~/.config/claudemd-forge/license",
]

_ENV_LICENSE_KEY = "ANCHORMD_LICENSE"
_LEGACY_ENV_LICENSE_KEY = "CLAUDEMD_FORGE_LICENSE"
_ENV_LICENSE_SERVER = "ANCHORMD_LICENSE_SERVER"
_ENV_STRICT_MODE = "ANCHORMD_STRICT"

# Cache settings.
_CACHE_DIR = Path("~/.anchormd").expanduser()
_CACHE_FILE = _CACHE_DIR / "license_cache.json"
_CACHE_TTL_SECONDS = 86400  # 24 hours
_SERVER_TIMEOUT_SECONDS = 5


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
            "drift_run",
            "drift_report",
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
            "drift_run",
            "drift_report",
            "drift_generate",
            "drift_llm_judge",
            "drift_fix",
            "drift_ci",
            "drift_html_report",
            "tech_debt",
            "github_health",
            "opsec",
            "cleanup",
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
        "drift_generate",
        "drift_llm_judge",
        "drift_fix",
        "drift_ci",
        "drift_html_report",
        "tech_debt",
        "github_health",
        "opsec",
        "cleanup",
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

    Format: ANMD-XXXX-XXXX-XXXX or legacy CMDF-XXXX-XXXX-XXXX.
    """
    key = key.strip()
    if not (key.startswith("ANMD-") or key.startswith("CMDF-")):
        return False
    parts = key.split("-")
    if len(parts) != 4:
        return False
    for part in parts[1:]:
        if len(part) != 4 or not part.isalnum() or part != part.upper():
            return False
    return True


def _compute_check_segment(body: str, salt: str | None = None) -> str:
    """Derive the expected check segment from the key body.

    The body is the two middle segments joined by a hyphen,
    e.g. "ABCD-EFGH" for key "ANMD-ABCD-EFGH-XXXX".
    Returns a 4-character uppercase hex string.
    """
    salt = salt or _KEY_SALT
    digest = hashlib.sha256(f"{salt}:{body}".encode()).hexdigest()
    return digest[:4].upper()


def _validate_key_checksum(key: str) -> bool:
    """Verify the key's check segment matches its body.

    Tries the current salt first, then the legacy salt for
    backward compatibility with CMDF- prefix keys.
    """
    parts = key.strip().split("-")
    if len(parts) != 4:
        return False
    body = f"{parts[1]}-{parts[2]}"
    # Try current salt
    if parts[3] == _compute_check_segment(body, _KEY_SALT):
        return True
    # Try legacy salt for CMDF- keys
    return parts[3] == _compute_check_segment(body, _LEGACY_KEY_SALT)


def _find_license_key() -> str | None:
    """Search for a license key in environment and filesystem."""
    # 1. Check environment variable (current, then legacy).
    for env_var in (_ENV_LICENSE_KEY, _LEGACY_ENV_LICENSE_KEY):
        env_key = os.environ.get(env_var)
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


def _get_license_server_url() -> str | None:
    """Return the configured license server URL, or None if unset."""
    return os.environ.get(_ENV_LICENSE_SERVER)


def _is_strict_mode() -> bool:
    """Check if strict licensing mode is active.

    In strict mode, the client will not grant Pro tier when the license server
    was never contacted (no URL configured or network failure with no cache).
    Keys with a valid local checksum but no server verification return FREE
    instead of fabricated Pro. Existing cached Pro info (even expired) is still
    honored since it was previously server-verified.
    """
    val = os.environ.get(_ENV_STRICT_MODE, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def _validate_with_server(key: str) -> LicenseInfo | None:
    """Call the license server to validate a key.

    Returns LicenseInfo on success, None on any failure (network, timeout, no httpx).
    httpx is lazy-imported so the server extra remains optional.
    """
    server_url = _get_license_server_url()
    if not server_url:
        return None

    try:
        import httpx  # noqa: F811
    except ImportError:
        logger.debug("httpx not installed — skipping server validation")
        return None

    try:
        from anchormd.machine_id import get_machine_id

        machine_id = get_machine_id()
    except Exception:
        machine_id = None

    try:
        resp = httpx.post(
            f"{server_url.rstrip('/')}/v1/validate",
            json={"license_key": key, "machine_id": machine_id},
            timeout=_SERVER_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            logger.debug("Server returned %d", resp.status_code)
            return None

        data = resp.json()
        tier = Tier.PRO if data.get("valid") else Tier.FREE
        return LicenseInfo(
            tier=tier,
            license_key=key,
            valid=data.get("valid", False),
            email=data.get("email"),
            metadata=data.get("metadata", {}),
        )
    except Exception:
        logger.debug("Server validation failed", exc_info=True)
        return None


def _load_cache(key: str) -> LicenseInfo | None:
    """Load cached license info if fresh (within TTL)."""
    try:
        if not _CACHE_FILE.is_file():
            return None
        data = json.loads(_CACHE_FILE.read_text())
        if data.get("key") != key:
            return None
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > _CACHE_TTL_SECONDS:
            return None
        return LicenseInfo(
            tier=Tier(data["tier"]),
            license_key=key,
            valid=data.get("valid", False),
            email=data.get("email"),
            metadata=data.get("metadata", {}),
        )
    except Exception:
        return None


def _load_cache_expired(key: str) -> LicenseInfo | None:
    """Load cached license info ignoring TTL (degraded mode)."""
    try:
        if not _CACHE_FILE.is_file():
            return None
        data = json.loads(_CACHE_FILE.read_text())
        if data.get("key") != key:
            return None
        info = LicenseInfo(
            tier=Tier(data["tier"]),
            license_key=key,
            valid=data.get("valid", False),
            email=data.get("email"),
            metadata={**data.get("metadata", {}), "degraded": True},
        )
        return info
    except Exception:
        return None


def _save_cache(key: str, info: LicenseInfo) -> None:
    """Persist license info to disk with restrictive permissions."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": key,
            "tier": str(info.tier),
            "valid": info.valid,
            "email": info.email,
            "metadata": info.metadata,
            "cached_at": time.time(),
        }
        _CACHE_FILE.write_text(json.dumps(payload))
        _CACHE_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except Exception:
        logger.debug("Failed to save license cache", exc_info=True)


def get_license_info() -> LicenseInfo:
    """Detect and validate the current license.

    Validation pipeline:
    1. Find key (env var / file) -> local format + checksum check
    2. Check fresh cache -> return on hit
    3. Call license server -> cache on success
    4. Server down -> use expired cache with degraded flag
    5. No cache available -> local-only validation (Pro if checksum passes)
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

    # Step 2: Check fresh cache.
    cached = _load_cache(key)
    if cached is not None:
        logger.debug("Using cached license info")
        return cached

    # Step 3: Call server.
    server_info = _validate_with_server(key)
    if server_info is not None:
        _save_cache(key, server_info)
        return server_info

    # Step 4: Server down — try expired cache.
    expired = _load_cache_expired(key)
    if expired is not None:
        logger.warning("License server unreachable, using cached license (degraded)")
        return expired

    # Step 5: Fall back to local-only validation.
    if _is_strict_mode():
        logger.warning("Strict mode: refusing to grant Pro without server verification")
        return LicenseInfo(
            tier=Tier.FREE,
            license_key=key,
            valid=False,
            metadata={"strict_refused": True},
        )
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
        f"'{feature}' requires AnchorMD Pro ({pro_config.price_label}).\n"
        f"Upgrade at: https://anchormd.dev/pro\n"
        f"Set your key via: export {_ENV_LICENSE_KEY}=ANMD-XXXX-XXXX-XXXX"
    )


def check_scan_quota(scan_type: str = "deep_scan") -> dict | None:
    """Check remaining scan quota against the license server.

    Returns dict with {used, limit, remaining, allowed, period} on success,
    None if server is unavailable or no key configured.
    """
    key = _find_license_key()
    if key is None:
        return {
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "allowed": scan_type == "audit",
            "period": "",
        }

    server_url = _get_license_server_url()
    if not server_url:
        return None  # No server configured — can't enforce quotas

    try:
        import httpx
    except ImportError:
        return None

    try:
        resp = httpx.post(
            f"{server_url}/v1/usage/check",
            json={"license_key": key, "scan_type": scan_type},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        logger.debug("Usage check failed", exc_info=True)

    return None  # Server unavailable — fail open


def record_scan(scan_type: str = "deep_scan", repo_fingerprint: str | None = None) -> dict | None:
    """Record a scan against the license server quota.

    Returns dict with {used, limit, remaining, allowed, period} on success,
    None if server is unavailable.
    """
    key = _find_license_key()
    if key is None:
        return None

    server_url = _get_license_server_url()
    if not server_url:
        return None

    try:
        import httpx
    except ImportError:
        return None

    try:
        resp = httpx.post(
            f"{server_url}/v1/usage",
            json={
                "license_key": key,
                "scan_type": scan_type,
                "repo_fingerprint": repo_fingerprint,
            },
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        logger.debug("Usage record failed", exc_info=True)

    return None
