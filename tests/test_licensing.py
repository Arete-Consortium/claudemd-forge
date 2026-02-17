"""Tests for the licensing and tier system."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from claudemd_forge.licensing import (
    PRO_FEATURES,
    PRO_PRESETS,
    TIER_DEFINITIONS,
    Tier,
    _compute_check_segment,
    _validate_key_checksum,
    _validate_key_format,
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
        assert _validate_key_format("CMDF-ABCD-EFGH-54EF") is True

    def test_valid_key_with_digits(self) -> None:
        assert _validate_key_format("CMDF-AB12-CD34-EF56") is True

    def test_invalid_prefix(self) -> None:
        assert _validate_key_format("XXXX-ABCD-EFGH-IJKL") is False

    def test_too_few_segments(self) -> None:
        assert _validate_key_format("CMDF-ABCD-EFGH") is False

    def test_too_many_segments(self) -> None:
        assert _validate_key_format("CMDF-ABCD-EFGH-54EF-MNOP") is False

    def test_lowercase_rejected(self) -> None:
        assert _validate_key_format("CMDF-abcd-EFGH-IJKL") is False

    def test_short_segment(self) -> None:
        assert _validate_key_format("CMDF-ABC-EFGH-IJKL") is False

    def test_empty_string(self) -> None:
        assert _validate_key_format("") is False

    def test_whitespace_stripped(self) -> None:
        assert _validate_key_format("  CMDF-ABCD-EFGH-54EF  ") is True


class TestKeyChecksum:
    def test_valid_checksum(self) -> None:
        assert _validate_key_checksum("CMDF-ABCD-EFGH-54EF") is True

    def test_invalid_checksum(self) -> None:
        # Valid format but wrong check segment.
        assert _validate_key_checksum("CMDF-ABCD-EFGH-XXXX") is False

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
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-XXXX",
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
                "claudemd_forge.licensing._find_license_key",
                return_value=None,
            ),
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False

    def test_env_var_valid_key(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            info = get_license_info()
            assert info.tier == Tier.PRO
            assert info.valid is True
            assert info.license_key == "CMDF-ABCD-EFGH-54EF"

    def test_invalid_key_stays_free(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="not-a-valid-key",
        ):
            info = get_license_info()
            assert info.tier == Tier.FREE
            assert info.valid is False

    def test_file_license_key(self, tmp_path: Path) -> None:
        license_file = tmp_path / ".claudemd-forge-license"
        license_file.write_text("CMDF-TEST-KEYS-3F80\n")

        with (
            patch(
                "claudemd_forge.licensing._LICENSE_LOCATIONS",
                [str(license_file)],
            ),
            patch.dict(os.environ, {}, clear=True),
            patch(
                "claudemd_forge.licensing.os.environ.get",
                return_value=None,
            ),
        ):
            from claudemd_forge.licensing import _find_license_key

            key = _find_license_key()
            # The patched location should be found.
            assert key is not None


class TestFeatureAccess:
    def test_free_has_generate(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            assert has_feature("generate") is True

    def test_free_lacks_diff(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            assert has_feature("diff") is False

    def test_pro_has_diff(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            assert has_feature("diff") is True

    def test_free_has_community_preset(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            assert has_preset_access("default") is True
            assert has_preset_access("python-fastapi") is True

    def test_free_lacks_premium_preset(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            assert has_preset_access("react-native") is False
            assert has_preset_access("data-science") is False

    def test_pro_has_premium_preset(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            assert has_preset_access("react-native") is True
            assert has_preset_access("data-science") is True


class TestIsPro:
    def test_free_tier(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            assert is_pro() is False

    def test_pro_tier(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
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
        assert "claudemd-forge.dev/pro" in msg

    def test_message_contains_env_var(self) -> None:
        msg = get_upgrade_message("diff")
        assert "CLAUDEMD_FORGE_LICENSE" in msg


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
