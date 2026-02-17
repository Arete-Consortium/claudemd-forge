"""Tests for feature gating decorators and helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from claudemd_forge.cli import app
from claudemd_forge.gates import (
    check_preset_access,
    get_available_presets,
)

runner = CliRunner()


class TestRequireProDecorator:
    def test_blocks_free_user(self) -> None:
        """Pro-gated commands should exit 1 for free users."""
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            # The init command is gated behind Pro.
            result = runner.invoke(app, ["init", "/tmp"])
            assert result.exit_code == 1
            assert "Pro" in result.output or "pro" in result.output.lower()

    def test_allows_pro_user(self) -> None:
        """Pro-gated commands should run for Pro users."""
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            # init will fail on path validation but should get past the gate.
            result = runner.invoke(app, ["init", "/nonexistent/path"])
            # Should NOT show upgrade message.
            assert "Upgrade" not in result.output

    def test_diff_blocked_for_free(self) -> None:
        """diff command should be blocked for free users."""
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            result = runner.invoke(app, ["diff", "/tmp"])
            assert result.exit_code == 1
            assert "Pro" in result.output or "pro" in result.output.lower()


class TestCheckPresetAccess:
    def test_free_preset_passes(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            # Should not raise for free presets.
            check_preset_access("default")
            check_preset_access("python-fastapi")

    def test_pro_preset_blocks_free_user(self) -> None:
        from click.exceptions import Exit

        with (
            patch(
                "claudemd_forge.licensing._find_license_key",
                return_value=None,
            ),
            pytest.raises(Exit),
        ):
            check_preset_access("react-native")

    def test_pro_preset_passes_for_pro_user(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            # Should not raise for Pro users.
            check_preset_access("react-native")
            check_preset_access("data-science")

    def test_unknown_preset_gives_not_found(self) -> None:
        """Unknown presets should say 'not found', not upsell to Pro."""
        from click.exceptions import Exit

        with (
            patch(
                "claudemd_forge.licensing._find_license_key",
                return_value=None,
            ),
            pytest.raises(Exit),
        ):
            check_preset_access("totally-fake-preset")

    def test_unknown_preset_message_not_pro(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Unknown preset error should not mention Pro upgrade."""
        from click.exceptions import Exit

        with (
            patch(
                "claudemd_forge.licensing._find_license_key",
                return_value=None,
            ),
            pytest.raises(Exit),
        ):
            check_preset_access("nonexistent")


class TestGetAvailablePresets:
    def test_free_user_sees_tiers(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            presets = get_available_presets()
            assert presets["default"] == "free"
            assert presets["react-native"] == "pro"

    def test_pro_user_sees_unlocked(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            presets = get_available_presets()
            assert presets["default"] == "free"
            assert presets["react-native"] == "unlocked"


class TestCLITierDisplay:
    def test_presets_shows_tier_column(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            result = runner.invoke(app, ["presets"])
            assert result.exit_code == 0
            assert "Tier" in result.output or "Free" in result.output

    def test_frameworks_shows_tier_column(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            result = runner.invoke(app, ["frameworks"])
            assert result.exit_code == 0
            assert "Tier" in result.output or "Free" in result.output

    def test_status_command(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value=None,
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "Free" in result.output

    def test_status_pro(self) -> None:
        with patch(
            "claudemd_forge.licensing._find_license_key",
            return_value="CMDF-ABCD-EFGH-54EF",
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "Pro" in result.output or "Valid" in result.output
