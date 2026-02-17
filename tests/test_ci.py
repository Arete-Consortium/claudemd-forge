"""Tests for the CI integration module."""

from __future__ import annotations

from pathlib import Path

from claudemd_forge.ci import generate_github_action, get_action_template


class TestGitHubAction:
    def test_template_is_valid_yaml_string(self) -> None:
        template = get_action_template()
        assert isinstance(template, str)
        assert len(template) > 100
        assert "name:" in template

    def test_template_has_required_sections(self) -> None:
        template = get_action_template()
        assert "pull_request" in template
        assert "claudemd-forge" in template
        assert "audit" in template
        assert "Comment on PR" in template

    def test_template_has_permissions(self) -> None:
        template = get_action_template()
        assert "pull-requests: write" in template
        assert "contents: read" in template

    def test_template_uses_env_vars_not_direct_interpolation(self) -> None:
        """Audit output must be passed via env vars, not ${{ }} in JS."""
        template = get_action_template()
        assert "process.env.AUDIT_OUTPUT" in template
        assert "process.env.AUDIT_EXIT_CODE" in template
        # Must NOT have direct interpolation in the script body.
        lines = template.split("\n")
        in_script = False
        for line in lines:
            if "script: |" in line:
                in_script = True
                continue
            if in_script:
                # Lines with less indentation end the script block.
                stripped = line.lstrip()
                if stripped and not line.startswith(" " * 14) and stripped[0] != "#":
                    break
                assert "${{" not in line, (
                    f"Direct interpolation in script body is a "
                    f"script injection risk: {line.strip()}"
                )

    def test_generate_creates_file(self, tmp_path: Path) -> None:
        result = generate_github_action(tmp_path)
        assert result.exists()
        assert result.name == "claudemd-audit.yml"
        assert result.parent.name == "workflows"

    def test_generate_creates_directory_structure(self, tmp_path: Path) -> None:
        generate_github_action(tmp_path)
        assert (tmp_path / ".github").is_dir()
        assert (tmp_path / ".github" / "workflows").is_dir()

    def test_generate_file_content_matches_template(self, tmp_path: Path) -> None:
        result = generate_github_action(tmp_path)
        content = result.read_text()
        assert content == get_action_template()

    def test_generate_overwrites_existing(self, tmp_path: Path) -> None:
        first = generate_github_action(tmp_path)
        first.write_text("old content")
        second = generate_github_action(tmp_path)
        assert second.read_text() == get_action_template()

    def test_generate_idempotent(self, tmp_path: Path) -> None:
        first = generate_github_action(tmp_path)
        second = generate_github_action(tmp_path)
        assert first == second
        assert first.read_text() == second.read_text()
