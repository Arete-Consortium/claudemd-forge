"""Docs consistency checks for user-facing version and licensing copy."""

from __future__ import annotations

from pathlib import Path

from anchormd import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_current_release_tag() -> None:
    content = (REPO_ROOT / "README.md").read_text()
    assert f"v{__version__}" in content
    assert "TODO: Add project description." not in content


def test_readme_and_landing_page_use_bsl_language() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    landing = (REPO_ROOT / "docs" / "index.html").read_text()
    assert "BSL-1.1" in readme
    assert "BSL-1.1" in landing


def test_marketing_drafts_do_not_claim_mit_license() -> None:
    docs = [
        REPO_ROOT / "docs" / "marketing" / "reddit-cursor.md",
        REPO_ROOT / "docs" / "marketing" / "show-hn.md",
        REPO_ROOT / "docs" / "marketing" / "substack.md",
    ]
    for path in docs:
        content = path.read_text()
        assert "MIT licensed" not in content
        assert "BSL-1.1" in content


def test_generator_sources_do_not_use_todo_overview_placeholder() -> None:
    sections = (REPO_ROOT / "src" / "anchormd" / "generators" / "sections.py").read_text()
    cli = (REPO_ROOT / "src" / "anchormd" / "cli.py").read_text()
    assert "TODO: Add project description." not in sections
    assert "TODO: Add project description." not in cli
