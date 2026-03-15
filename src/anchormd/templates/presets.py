"""Curated preset packs for common project types."""

from __future__ import annotations

from anchormd.models import PresetPack

PRESET_PACKS: dict[str, PresetPack] = {
    "default": PresetPack(
        name="Default",
        description="Auto-detect framework and apply matching preset",
        auto_detect=True,
    ),
    "monorepo": PresetPack(
        name="Monorepo",
        description="Multi-package repository with shared conventions",
        extra_sections=["Workspace Structure", "Package Dependencies"],
    ),
    "library": PresetPack(
        name="Library/Package",
        description="Published library with API docs focus",
        extra_sections=["Public API", "Versioning Policy", "Release Process"],
    ),
    "minimal": PresetPack(
        name="Minimal",
        description="Bare essentials only — overview, commands, anti-patterns",
        sections=["header", "current_state", "common_commands", "anti_patterns"],
    ),
    "full": PresetPack(
        name="Full",
        description="All sections included with maximum detail",
    ),
}
