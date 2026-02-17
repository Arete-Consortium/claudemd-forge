"""Tests for template system and framework presets."""

from __future__ import annotations

from claudemd_forge.templates.base import BaseTemplate
from claudemd_forge.templates.frameworks import FRAMEWORK_PRESETS, PREMIUM_PRESETS
from claudemd_forge.templates.presets import PRESET_PACKS


class TestBaseTemplate:
    def test_available_sections(self) -> None:
        sections = BaseTemplate.available_sections()
        assert "header" in sections
        assert "common_commands" in sections
        assert len(sections) > 5

    def test_render_header(self) -> None:
        result = BaseTemplate.render_section(
            "header", project_name="MyProject", description="A cool tool"
        )
        assert "# CLAUDE.md — MyProject" in result
        assert "A cool tool" in result

    def test_render_current_state(self) -> None:
        result = BaseTemplate.render_section(
            "current_state",
            phase="alpha",
            version="0.1.0",
            primary_language="Python",
            total_files=42,
            language_count=3,
        )
        assert "Python" in result
        assert "42" in result

    def test_render_unknown_section(self) -> None:
        result = BaseTemplate.render_section("nonexistent")
        assert result == ""

    def test_render_is_deterministic(self) -> None:
        a = BaseTemplate.render_section("header", project_name="X", description="Y")
        b = BaseTemplate.render_section("header", project_name="X", description="Y")
        assert a == b


class TestFrameworkPresets:
    def test_at_least_eight_presets(self) -> None:
        assert len(FRAMEWORK_PRESETS) >= 8

    def test_all_presets_have_required_fields(self) -> None:
        for name, preset in FRAMEWORK_PRESETS.items():
            assert preset.name, f"{name} missing name"
            assert preset.description, f"{name} missing description"
            assert len(preset.coding_standards) > 0, f"{name} missing coding standards"
            assert len(preset.anti_patterns) > 0, f"{name} missing anti-patterns"
            assert len(preset.common_commands) > 0, f"{name} missing commands"

    def test_python_fastapi_preset(self) -> None:
        preset = FRAMEWORK_PRESETS["python-fastapi"]
        assert "async" in " ".join(preset.coding_standards).lower()
        assert any("pydantic" in s.lower() for s in preset.coding_standards)

    def test_react_typescript_preset(self) -> None:
        preset = FRAMEWORK_PRESETS["react-typescript"]
        assert any("hooks" in s.lower() for s in preset.coding_standards)
        assert any("class component" in s.lower() for s in preset.anti_patterns)

    def test_rust_preset(self) -> None:
        preset = FRAMEWORK_PRESETS["rust"]
        assert any("unwrap" in s.lower() for s in preset.anti_patterns)
        assert "cargo build" in preset.common_commands.values()

    def test_all_render_valid_markdown(self) -> None:
        """All presets should produce valid markdown-like strings."""
        for _name, preset in FRAMEWORK_PRESETS.items():
            # Standards should all be non-empty strings.
            for std in preset.coding_standards:
                assert isinstance(std, str) and len(std) > 0
            for ap in preset.anti_patterns:
                assert isinstance(ap, str) and ap.startswith("Do NOT")
            for _cmd_name, cmd in preset.common_commands.items():
                assert isinstance(cmd, str) and len(cmd) > 0

    def test_deterministic_rendering(self) -> None:
        """Same preset produces same output each time."""
        p1 = FRAMEWORK_PRESETS["rust"]
        p2 = FRAMEWORK_PRESETS["rust"]
        assert p1 == p2


class TestPresetPacks:
    def test_default_pack_auto_detects(self) -> None:
        pack = PRESET_PACKS["default"]
        assert pack.auto_detect is True

    def test_minimal_pack_has_fewer_sections(self) -> None:
        minimal = PRESET_PACKS["minimal"]
        assert minimal.sections is not None
        assert len(minimal.sections) < 8

    def test_all_packs_have_required_fields(self) -> None:
        for name, pack in PRESET_PACKS.items():
            assert pack.name, f"{name} missing name"
            assert pack.description, f"{name} missing description"

    def test_unknown_framework_falls_back(self) -> None:
        """Requesting a non-existent framework should not crash."""
        result = FRAMEWORK_PRESETS.get("nonexistent-framework")
        assert result is None  # Graceful fallback.


class TestPremiumPresets:
    def test_at_least_four_premium_presets(self) -> None:
        assert len(PREMIUM_PRESETS) >= 4

    def test_all_premium_presets_have_required_fields(self) -> None:
        for name, preset in PREMIUM_PRESETS.items():
            assert preset.name, f"{name} missing name"
            assert preset.description, f"{name} missing description"
            assert len(preset.coding_standards) > 0, f"{name} missing coding standards"
            assert len(preset.anti_patterns) > 0, f"{name} missing anti-patterns"
            assert len(preset.common_commands) > 0, f"{name} missing commands"

    def test_react_native_preset(self) -> None:
        preset = PREMIUM_PRESETS["react-native"]
        assert any("hooks" in s.lower() for s in preset.coding_standards)
        assert any("stylesheet" in s.lower() for s in preset.anti_patterns)

    def test_data_science_preset(self) -> None:
        preset = PREMIUM_PRESETS["data-science"]
        assert any("notebook" in s.lower() for s in preset.coding_standards)

    def test_devops_preset(self) -> None:
        preset = PREMIUM_PRESETS["devops"]
        assert any(
            "terraform" in s.lower() or "declarative" in s.lower() for s in preset.coding_standards
        )

    def test_mobile_preset(self) -> None:
        preset = PREMIUM_PRESETS["mobile"]
        assert any("platform" in s.lower() for s in preset.coding_standards)

    def test_premium_anti_patterns_format(self) -> None:
        """All premium preset anti-patterns start with 'Do NOT'."""
        for _name, preset in PREMIUM_PRESETS.items():
            for ap in preset.anti_patterns:
                assert ap.startswith("Do NOT"), f"Bad format: {ap}"

    def test_no_overlap_with_community(self) -> None:
        """Premium preset keys should not conflict with community ones."""
        for name in PREMIUM_PRESETS:
            assert name not in FRAMEWORK_PRESETS
