"""Tests for the licensing and tier system."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from anchormd.licensing import (
    PRO_FEATURES,
    PRO_PRESETS,
    TIER_DEFINITIONS,
    LicenseInfo,
    Tier,
    _compute_check_segment,
    _load_cache,
    _load_cache_expired,
    _save_cache,
    _validate_key_checksum,
    _validate_key_format,
    _validate_with_server,
    get_license_info,
    get_upgrade_message,
    has_feature,
    has_preset_access,
    is_known_preset,
    is_pro,
)


class TestTierDefinitions:
    def test_free_tier_exists(self) -> None:
        assert Tier.FREE in TIER_DEFINITIONS

    def test_pro_tier_exists(self) -> None:
        assert Tier.PRO in TIER_DEFINITIONS

    def test_free_tier_has_core_features(self) -> None:
        free = TIER_DEFINITIONS[Tier.FREE]
        assert "generate" in free.features
        assert "audit" in free.features
        assert "presets" in free.features
        assert "frameworks" in free.features

    def test_pro_tier_has_all_free_features(self) -> None:
        free = TIER_DEFINITIONS[Tier.FREE]
        pro = TIER_DEFINITIONS[Tier.PRO]
        for feature in free.features:
            assert feature in pro.features

    def test_pro_tier_has_exclusive_features(self) -> None:
        pro = TIER_DEFINITIONS[Tier.PRO]
        assert "init_interactive" in pro.features
        assert "diff" in pro.features
        assert "ci_integration" in pro.features
        assert "premium_presets" in pro.features

    def test_tier_config_has_price(self) -> None:
        for tier_config in TIER_DEFINITIONS.values():
            assert tier_config.price_label

    def test_pro_presets_not_in_free(self) -> None:
        free = TIER_DEFINITIONS[Tier.FREE]
        for preset in PRO_PRESETS:
            assert preset not in free.preset_access


class TestKeyValidation:
    def test_valid_key(self) -> None:
        assert _validate_key_format("ANMD-ABCD-EFGH-32E3") is True

    def test_valid_key_with_digits(self) -> None:
        assert _validate_key_format("ANMD-AB12-CD34-EF56") is True

    def test_invalid_prefix(self) -> None:
        assert _validate_key_format("XXXX-ABCD-EFGH-IJKL") is False

    def test_too_few_segments(self) -> None:
        assert _validate_key_format("ANMD-ABCD-EFGH") is False

    def test_too_many_segments(self) -> None:
        assert _validate_key_format("ANMD-ABCD-EFGH-32E3-MNOP") is False

    def test_lowercase_rejected(self) -> None:
        assert _validate_key_format("ANMD-abcd-EFGH-IJKL") is False

    def test_short_segment(self) -> None:
        assert _validate_key_format("ANMD-ABC-EFGH-IJKL") is False

    def test_empty_string(self) -> None:
        assert _validate_key_format("") is False

    def test_whitespace_stripped(self) -> None:
        assert _validate_key_format("  ANMD-ABCD-EFGH-32E3  ") is True

    def test_legacy_cmdf_prefix_accepted(self) -> None:
        assert _validate_key_format("CMDF-ABCD-EFGH-54EF") is True


class TestKeyChecksum:
    def test_valid_checksum(self) -> None:
        assert _validate_key_checksum("ANMD-ABCD-EFGH-32E3") is True

    def test_legacy_cmdf_checksum(self) -> None:
        # CMDF- keys with old salt should still validate
        assert _validate_key_checksum("CMDF-ABCD-EFGH-54EF") is True

    def test_invalid_checksum(self) -> None:
        # Valid format but wrong check segment.
        assert _validate_key_checksum("ANMD-ABCD-EFGH-XXXX") is False

    def test_checksum_is_deterministic(self) -> None:
        seg = _compute_check_segment("ABCD-EFGH")
        assert seg == _compute_check_segment("ABCD-EFGH")

    def test_checksum_differs_for_different_bodies(self) -> None:
        seg1 = _compute_check_segment("ABCD-EFGH")
        seg2 = _compute_check_segment("WXYZ-QRST")
        assert seg1 != seg2

    def test_checksum_is_4_chars_uppercase_hex(self) -> None:
        seg = _compute_check_segment("ABCD-EFGH")
        assert len(seg) == 4
        assert seg == seg.upper()
        # Must be valid hex.
        int(seg, 16)

    def test_format_valid_but_bad_checksum_stays_free(self) -> None:
        """A key that passes format validation but fails checksum stays free."""
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="ANMD-ABCD-EFGH-XXXX",
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False


class TestKnownPreset:
    def test_community_preset_is_known(self) -> None:
        assert is_known_preset("default") is True

    def test_pro_preset_is_known(self) -> None:
        assert is_known_preset("react-native") is True

    def test_unknown_preset(self) -> None:
        assert is_known_preset("totally-fake-preset") is False


class TestLicenseDetection:
    def test_no_key_returns_free(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "anchormd.licensing._find_license_key",
                return_value=None,
            ),
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False

    def test_env_var_valid_key(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="ANMD-ABCD-EFGH-32E3",
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True
            assert info.license_key == "ANMD-ABCD-EFGH-32E3"

    def test_invalid_key_stays_free(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="not-a-valid-key",
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False

    def test_file_license_key(self, tmp_path: Path) -> None:
        license_file = tmp_path / ".anchormd-license"
        license_file.write_text("ANMD-TEST-KEYS-187C\n")

        with (
            patch(
                "anchormd.licensing._LICENSE_LOCATIONS",
                [str(license_file)],
            ),
            patch.dict(os.environ, {}, clear=True),
            patch(
                "anchormd.licensing.os.environ.get",
                return_value=None,
            ),
        ):
            from anchormd.licensing import _find_license_key

            key = _find_license_key()
            # The patched location should be found.
            assert key is not None


class TestFeatureAccess:
    def test_free_has_generate(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value=None,
        ):
            assert has_feature("generate") is True

    def test_free_lacks_diff(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value=None,
        ):
            assert has_feature("diff") is False

    def test_pro_has_diff(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="ANMD-ABCD-EFGH-32E3",
        ):
            assert has_feature("diff") is True

    def test_free_has_community_preset(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value=None,
        ):
            assert has_preset_access("default") is True
            assert has_preset_access("python-fastapi") is True

    def test_free_lacks_premium_preset(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value=None,
        ):
            assert has_preset_access("react-native") is False
            assert has_preset_access("data-science") is False

    def test_pro_has_premium_preset(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="ANMD-ABCD-EFGH-32E3",
        ):
            assert has_preset_access("react-native") is True
            assert has_preset_access("data-science") is True


class TestIsPro:
    def test_free_tier(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value=None,
        ):
            assert is_pro() is False

    def test_pro_tier(self) -> None:
        with patch(
            "anchormd.licensing._find_license_key",
            return_value="ANMD-ABCD-EFGH-32E3",
        ):
            assert is_pro() is True


class TestUpgradeMessage:
    def test_message_contains_feature(self) -> None:
        msg = get_upgrade_message("diff")
        assert "diff" in msg

    def test_message_contains_price(self) -> None:
        msg = get_upgrade_message("diff")
        assert "$8/mo" in msg

    def test_message_contains_url(self) -> None:
        msg = get_upgrade_message("diff")
        assert "anchormd.dev/pro" in msg

    def test_message_contains_env_var(self) -> None:
        msg = get_upgrade_message("diff")
        assert "ANCHORMD_LICENSE" in msg


class TestProFeatureConstants:
    def test_pro_features_are_frozen(self) -> None:
        assert isinstance(PRO_FEATURES, frozenset)

    def test_pro_presets_are_frozen(self) -> None:
        assert isinstance(PRO_PRESETS, frozenset)

    def test_pro_features_match_tier_diff(self) -> None:
        free_features = set(TIER_DEFINITIONS[Tier.FREE].features)
        pro_features = set(TIER_DEFINITIONS[Tier.PRO].features)
        exclusive = pro_features - free_features
        assert exclusive == PRO_FEATURES


# --- Server validation tests ---

_VALID_KEY = "ANMD-ABCD-EFGH-32E3"


class TestValidateWithServer:
    def test_no_server_url_returns_none(self) -> None:
        with patch("anchormd.licensing._get_license_server_url", return_value=None):
            result = _validate_with_server(_VALID_KEY)
            assert result is None

    def test_httpx_not_installed_returns_none(self) -> None:
        with (
            patch("anchormd.licensing._get_license_server_url", return_value="http://x"),
            patch.dict("sys.modules", {"httpx": None}),
        ):
            result = _validate_with_server(_VALID_KEY)
            assert result is None

    def test_server_success_returns_info(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "valid": True,
            "tier": "pro",
            "email": "test@test.com",
            "metadata": {},
        }
        mock_httpx = MagicMock()
        mock_httpx.post.return_value = mock_resp

        with (
            patch("anchormd.licensing._get_license_server_url", return_value="http://x"),
            patch.dict("sys.modules", {"httpx": mock_httpx}),
        ):
            result = _validate_with_server(_VALID_KEY)
            assert result is not None
            assert result.tier == Tier.PRO
            assert result.valid is True
            assert result.email == "test@test.com"

    def test_server_invalid_key(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"valid": False, "tier": "free"}
        mock_httpx = MagicMock()
        mock_httpx.post.return_value = mock_resp

        with (
            patch("anchormd.licensing._get_license_server_url", return_value="http://x"),
            patch.dict("sys.modules", {"httpx": mock_httpx}),
        ):
            result = _validate_with_server(_VALID_KEY)
            assert result is not None
            assert result.tier == Tier.FREE
            assert result.valid is False

    def test_server_error_returns_none(self) -> None:
        mock_httpx = MagicMock()
        mock_httpx.post.side_effect = ConnectionError("refused")

        with (
            patch("anchormd.licensing._get_license_server_url", return_value="http://x"),
            patch.dict("sys.modules", {"httpx": mock_httpx}),
        ):
            result = _validate_with_server(_VALID_KEY)
            assert result is None

    def test_server_non_200_returns_none(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_httpx = MagicMock()
        mock_httpx.post.return_value = mock_resp

        with (
            patch("anchormd.licensing._get_license_server_url", return_value="http://x"),
            patch.dict("sys.modules", {"httpx": mock_httpx}),
        ):
            result = _validate_with_server(_VALID_KEY)
            assert result is None


class TestCache:
    def test_save_and_load(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        info = LicenseInfo(tier=Tier.PRO, license_key=_VALID_KEY, valid=True, email="t@t.com")

        with (
            patch("anchormd.licensing._CACHE_DIR", tmp_path),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
        ):
            _save_cache(_VALID_KEY, info)
            assert cache_file.exists()

            loaded = _load_cache(_VALID_KEY)
            assert loaded is not None
            assert loaded.tier == Tier.PRO
            assert loaded.valid is True

    def test_cache_expired_returns_none(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": None,
            "metadata": {},
            "cached_at": time.time() - 100000,  # way past TTL
        }
        cache_file.write_text(json.dumps(payload))

        with patch("anchormd.licensing._CACHE_FILE", cache_file):
            result = _load_cache(_VALID_KEY)
            assert result is None

    def test_cache_wrong_key_returns_none(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": "ANMD-XXXX-YYYY-ZZZZ",
            "tier": "pro",
            "valid": True,
            "cached_at": time.time(),
        }
        cache_file.write_text(json.dumps(payload))

        with patch("anchormd.licensing._CACHE_FILE", cache_file):
            result = _load_cache(_VALID_KEY)
            assert result is None

    def test_corrupt_cache_returns_none(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("not json at all {{{")

        with patch("anchormd.licensing._CACHE_FILE", cache_file):
            result = _load_cache(_VALID_KEY)
            assert result is None

    def test_no_cache_file_returns_none(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "nonexistent.json"

        with patch("anchormd.licensing._CACHE_FILE", cache_file):
            result = _load_cache(_VALID_KEY)
            assert result is None

    def test_load_expired_ignores_ttl(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": "t@t.com",
            "metadata": {},
            "cached_at": time.time() - 100000,
        }
        cache_file.write_text(json.dumps(payload))

        with patch("anchormd.licensing._CACHE_FILE", cache_file):
            result = _load_cache_expired(_VALID_KEY)
            assert result is not None
            assert result.tier == Tier.PRO
            assert result.metadata.get("degraded") is True

    def test_save_creates_dir(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "nested" / "dir"
        cache_file = cache_dir / "cache.json"
        info = LicenseInfo(tier=Tier.PRO, valid=True)

        with (
            patch("anchormd.licensing._CACHE_DIR", cache_dir),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
        ):
            _save_cache(_VALID_KEY, info)
            assert cache_dir.exists()

    def test_save_sets_permissions(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        info = LicenseInfo(tier=Tier.PRO, valid=True)

        with (
            patch("anchormd.licensing._CACHE_DIR", tmp_path),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
        ):
            _save_cache(_VALID_KEY, info)
            mode = cache_file.stat().st_mode
            assert mode & 0o777 == 0o600


class TestServerValidationPipeline:
    """Test the full get_license_info() flow with server integration."""

    def test_fresh_cache_hit_skips_server(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": "cached@t.com",
            "metadata": {},
            "cached_at": time.time(),
        }
        cache_file.write_text(json.dumps(payload))

        with (
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
            patch("anchormd.licensing._validate_with_server") as mock_server,
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.email == "cached@t.com"
            mock_server.assert_not_called()

    def test_server_result_cached(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        server_info = LicenseInfo(
            tier=Tier.PRO, license_key=_VALID_KEY, valid=True, email="server@t.com"
        )

        with (
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
            patch("anchormd.licensing._CACHE_DIR", tmp_path),
            patch("anchormd.licensing._validate_with_server", return_value=server_info),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert cache_file.exists()

    def test_server_down_uses_expired_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": "expired@t.com",
            "metadata": {},
            "cached_at": time.time() - 100000,
        }
        cache_file.write_text(json.dumps(payload))

        with (
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
            patch("anchormd.licensing._validate_with_server", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.metadata.get("degraded") is True

    def test_no_server_no_cache_falls_back_to_local(self) -> None:
        with (
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._load_cache", return_value=None),
            patch("anchormd.licensing._validate_with_server", return_value=None),
            patch("anchormd.licensing._load_cache_expired", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True


class TestStrictMode:
    """Strict mode refuses fail-open when the server never verified the key."""

    def test_strict_refuses_local_only_pro(self) -> None:
        with (
            patch.dict(os.environ, {"ANCHORMD_STRICT": "1"}, clear=False),
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._load_cache", return_value=None),
            patch("anchormd.licensing._validate_with_server", return_value=None),
            patch("anchormd.licensing._load_cache_expired", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False
            assert info.metadata.get("strict_refused") is True

    def test_strict_still_honors_fresh_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": "fresh@t.com",
            "metadata": {},
            "cached_at": time.time(),
        }
        cache_file.write_text(json.dumps(payload))

        with (
            patch.dict(os.environ, {"ANCHORMD_STRICT": "true"}, clear=False),
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True

    def test_strict_still_honors_expired_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        payload = {
            "key": _VALID_KEY,
            "tier": "pro",
            "valid": True,
            "email": "expired@t.com",
            "metadata": {},
            "cached_at": time.time() - 100000,
        }
        cache_file.write_text(json.dumps(payload))

        with (
            patch.dict(os.environ, {"ANCHORMD_STRICT": "1"}, clear=False),
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._CACHE_FILE", cache_file),
            patch("anchormd.licensing._validate_with_server", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.metadata.get("degraded") is True

    def test_strict_disabled_by_default(self) -> None:
        env_without_strict = {k: v for k, v in os.environ.items() if k != "ANCHORMD_STRICT"}
        with (
            patch.dict(os.environ, env_without_strict, clear=True),
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._load_cache", return_value=None),
            patch("anchormd.licensing._validate_with_server", return_value=None),
            patch("anchormd.licensing._load_cache_expired", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True

    def test_strict_off_value_does_not_trigger(self) -> None:
        with (
            patch.dict(os.environ, {"ANCHORMD_STRICT": "0"}, clear=False),
            patch("anchormd.licensing._find_license_key", return_value=_VALID_KEY),
            patch("anchormd.licensing._load_cache", return_value=None),
            patch("anchormd.licensing._validate_with_server", return_value=None),
            patch("anchormd.licensing._load_cache_expired", return_value=None),
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True
