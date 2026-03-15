"""Tests for the GitHub cleanup agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from anchormd.cleanup import CleanupAction, CleanupAgent, CleanupPlan


class TestCleanupPlan:
    def test_empty_plan(self) -> None:
        plan = CleanupPlan()
        assert plan.total == 0
        assert plan.executed_count == 0
        assert plan.error_count == 0
        assert plan.dry_run is True

    def test_plan_counts(self) -> None:
        plan = CleanupPlan(
            actions=[
                CleanupAction(action="close_issue", target="#1", reason="stale"),
                CleanupAction(action="close_pr", target="PR #2", reason="stale", executed=True),
                CleanupAction(
                    action="delete_branch",
                    target="branch `feat`",
                    reason="merged",
                    error="failed",
                ),
            ]
        )
        assert plan.total == 3
        assert plan.executed_count == 1
        assert plan.error_count == 1


class TestCleanupAgentPlan:
    def test_finds_stale_issues(self) -> None:
        mock_issues = [
            {
                "number": 1,
                "title": "Old issue",
                "updatedAt": "2025-01-01T00:00:00Z",
                "labels": [],
            },
            {
                "number": 2,
                "title": "Recent issue",
                "updatedAt": "2026-03-14T00:00:00Z",
                "labels": [],
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "issue" in args and "list" in args:
                return mock_issues
            return None

        with patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json):
            agent = CleanupAgent(cwd="/tmp", stale_issue_days=90)
            plan = agent.plan()

            stale_issues = [a for a in plan.actions if a.action == "close_issue"]
            assert len(stale_issues) == 1
            assert "#1" in stale_issues[0].target

    def test_finds_stale_prs(self) -> None:
        mock_prs = [
            {
                "number": 10,
                "title": "Old PR",
                "updatedAt": "2025-06-01T00:00:00Z",
                "isDraft": False,
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "pr" in args and "list" in args:
                return mock_prs
            return None

        with patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json):
            agent = CleanupAgent(cwd="/tmp", stale_pr_days=30)
            plan = agent.plan()

            stale_prs = [a for a in plan.actions if a.action == "close_pr"]
            assert len(stale_prs) == 1
            assert "#10" in stale_prs[0].target

    def test_skips_draft_prs_by_default(self) -> None:
        mock_prs = [
            {
                "number": 10,
                "title": "Draft PR",
                "updatedAt": "2025-06-01T00:00:00Z",
                "isDraft": True,
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "pr" in args and "list" in args:
                return mock_prs
            return None

        with patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json):
            agent = CleanupAgent(cwd="/tmp", close_draft_prs=False)
            plan = agent.plan()

            close_actions = [a for a in plan.actions if a.action == "close_pr"]
            assert len(close_actions) == 0

    def test_includes_draft_prs_when_enabled(self) -> None:
        mock_prs = [
            {
                "number": 10,
                "title": "Draft PR",
                "updatedAt": "2025-06-01T00:00:00Z",
                "isDraft": True,
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "pr" in args and "list" in args:
                return mock_prs
            return None

        with patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json):
            agent = CleanupAgent(cwd="/tmp", close_draft_prs=True, stale_pr_days=30)
            plan = agent.plan()

            close_actions = [a for a in plan.actions if a.action == "close_pr"]
            assert len(close_actions) == 1
            assert "Draft" in close_actions[0].target

    def test_finds_merged_branches(self) -> None:
        mock_prs = [
            {
                "number": 5,
                "headRefName": "feat/old-feature",
                "mergedAt": "2026-03-01T00:00:00Z",
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "pr" in args and "merged" in args:
                return mock_prs
            return None

        mock_git_result = MagicMock()
        mock_git_result.stdout = "origin/main\norigin/feat/old-feature\n"

        with (
            patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json),
            patch("subprocess.run", return_value=mock_git_result),
        ):
            agent = CleanupAgent(cwd="/tmp", delete_merged_branches=True)
            plan = agent.plan()

            branch_actions = [a for a in plan.actions if a.action == "delete_branch"]
            assert len(branch_actions) == 1
            assert "feat/old-feature" in branch_actions[0].target

    def test_protects_main_branch(self) -> None:
        mock_prs = [
            {"number": 5, "headRefName": "main", "mergedAt": "2026-03-01T00:00:00Z"},
        ]

        def mock_gh_json(args, cwd=None):
            if "pr" in args and "merged" in args:
                return mock_prs
            return None

        mock_git_result = MagicMock()
        mock_git_result.stdout = "origin/main\n"

        with (
            patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json),
            patch("subprocess.run", return_value=mock_git_result),
        ):
            agent = CleanupAgent(cwd="/tmp")
            plan = agent.plan()

            branch_actions = [a for a in plan.actions if a.action == "delete_branch"]
            assert len(branch_actions) == 0

    def test_no_branch_cleanup_when_disabled(self) -> None:
        agent = CleanupAgent(cwd="/tmp", delete_merged_branches=False)
        plan = CleanupPlan()
        agent._plan_merged_branches(plan)
        assert len(plan.actions) == 0

    def test_empty_when_no_stale(self) -> None:
        mock_issues = [
            {
                "number": 1,
                "title": "Fresh",
                "updatedAt": "2026-03-14T00:00:00Z",
                "labels": [],
            },
        ]
        mock_prs = [
            {
                "number": 1,
                "title": "Fresh PR",
                "updatedAt": "2026-03-14T00:00:00Z",
                "isDraft": False,
            },
        ]

        def mock_gh_json(args, cwd=None):
            if "issue" in args:
                return mock_issues
            if "pr" in args and "open" in args:
                return mock_prs
            if "pr" in args and "merged" in args:
                return []
            return None

        with patch("anchormd.cleanup._run_gh_json", side_effect=mock_gh_json):
            agent = CleanupAgent(cwd="/tmp")
            plan = agent.plan()
            assert plan.total == 0


class TestCleanupExecution:
    def test_execute_marks_actions(self) -> None:
        plan = CleanupPlan(
            actions=[
                CleanupAction(action="close_issue", target="#1: test", reason="stale"),
            ]
        )

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("anchormd.cleanup._run_gh", return_value=mock_result):
            agent = CleanupAgent(cwd="/tmp")
            agent.execute(plan)

            assert plan.actions[0].executed is True
            assert plan.dry_run is False

    def test_execute_captures_errors(self) -> None:
        plan = CleanupPlan(
            actions=[
                CleanupAction(action="close_issue", target="#1: test", reason="stale"),
            ]
        )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "not found"

        with patch("anchormd.cleanup._run_gh", return_value=mock_result):
            agent = CleanupAgent(cwd="/tmp")
            agent.execute(plan)

            assert plan.actions[0].executed is False
            assert plan.actions[0].error is not None
            assert plan.error_count == 1
