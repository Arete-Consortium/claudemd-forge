"""Tests for the GitHub analyzer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from anchormd.analyzers.github import GitHubAnalyzer
from anchormd.models import ForgeConfig, ProjectStructure


def _make_structure(root: Path = Path("/tmp/fake")) -> ProjectStructure:
    return ProjectStructure(
        root=root,
        files=[],
        directories=[],
        total_files=10,
        total_lines=200,
        primary_language="Python",
    )


def _make_config(root: Path = Path("/tmp/fake")) -> ForgeConfig:
    return ForgeConfig(root_path=root)


class TestGitHubAnalyzerNoGh:
    """Tests when gh CLI is unavailable or repo is not GitHub."""

    def test_not_github_repo(self) -> None:
        with patch("anchormd.analyzers.github._run_gh", return_value=None):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())
            assert result.category == "github"
            assert result.findings["available"] is False
            assert result.confidence == 0.0
            assert result.section_content == ""


class TestGitHubAnalyzerMocked:
    """Tests with mocked gh responses."""

    def _mock_repo_view(self) -> dict:
        return {
            "name": "anchormd",
            "owner": {"login": "AreteDriver"},
            "defaultBranchRef": {"name": "main"},
            "isPrivate": False,
            "stargazerCount": 42,
            "forkCount": 5,
            "licenseInfo": {"name": "MIT License"},
            "pushedAt": "2026-03-14T00:00:00Z",
        }

    def test_basic_repo_info(self) -> None:
        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return self._mock_repo_view()
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            assert result.findings["available"] is True
            assert result.findings["repo"] == "AreteDriver/anchormd"
            assert result.findings["stars"] == 42
            assert result.findings["license"] == "MIT License"

    def test_health_score_perfect(self) -> None:
        """Test health score with no issues."""

        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return self._mock_repo_view()
            if "issue" in args and "list" in args:
                return []
            if "pr" in args and "list" in args:
                return []
            if "release" in args:
                return [{"tagName": "v1.0.0", "publishedAt": "2026-03-14T00:00:00Z"}]
            if "run" in args:
                return [{"workflowName": "CI", "conclusion": "success"}]
            if "api" in args and "protection" in args[-1]:
                return {"url": "...", "required_pull_request_reviews": True}
            if "api" in args and "dependabot" in str(args):
                return []
            if "api" in args and "code-scanning" in str(args):
                return []
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            assert result.findings["health_score"] >= 90

    def test_health_score_degraded(self) -> None:
        """Test health score with problems."""

        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return self._mock_repo_view()
            if "issue" in args and "list" in args:
                return [
                    {
                        "number": 1,
                        "title": "old",
                        "updatedAt": "2025-01-01T00:00:00Z",
                        "labels": [],
                    }
                    for _ in range(5)
                ]
            if "pr" in args and "list" in args:
                return [
                    {
                        "number": 1,
                        "title": "stale",
                        "updatedAt": "2025-06-01T00:00:00Z",
                        "isDraft": False,
                    }
                    for _ in range(3)
                ]
            if "run" in args:
                return [{"workflowName": "CI", "conclusion": "failure"}]
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            assert result.findings["health_score"] < 80
            assert result.findings["issues"]["stale_90d"] == 5
            assert result.findings["workflows"]["failing"] == ["CI"]

    def test_section_content_rendered(self) -> None:
        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return self._mock_repo_view()
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            assert "## GitHub Health" in result.section_content
            assert "AreteDriver/anchormd" in result.section_content

    def test_no_license_deduction(self) -> None:
        repo = self._mock_repo_view()
        repo["licenseInfo"] = None

        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return repo
            if "api" in args and "protection" in args[-1]:
                return {"url": "...", "required_pull_request_reviews": True}
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            # Should lose 5 points for no license
            assert result.findings["health_score"] <= 95


class TestIssueDetection:
    def test_stale_issue_categorization(self) -> None:
        def mock_run_gh(args, cwd=None):
            if "repo" in args and "view" in args:
                return {
                    "name": "test",
                    "owner": {"login": "user"},
                    "defaultBranchRef": {"name": "main"},
                    "stargazerCount": 0,
                    "forkCount": 0,
                }
            if "issue" in args and "list" in args:
                return [
                    {
                        "number": 1,
                        "title": "fresh",
                        "updatedAt": "2026-03-10T00:00:00Z",
                        "labels": [],
                    },
                    {
                        "number": 2,
                        "title": "month-old",
                        "updatedAt": "2026-01-01T00:00:00Z",
                        "labels": [],
                    },
                    {
                        "number": 3,
                        "title": "ancient",
                        "updatedAt": "2025-06-01T00:00:00Z",
                        "labels": [],
                    },
                ]
            return None

        with patch("anchormd.analyzers.github._run_gh", side_effect=mock_run_gh):
            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(_make_structure(), _make_config())

            issues = result.findings["issues"]
            assert issues["open"] == 3
            assert issues["stale_30d"] == 1  # month-old
            assert issues["stale_90d"] == 1  # ancient
