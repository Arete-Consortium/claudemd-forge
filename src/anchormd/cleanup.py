"""GitHub repository cleanup agent — closes stale artifacts via gh CLI."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_GH_TIMEOUT = 15


@dataclass
class CleanupAction:
    """A single cleanup action to be taken."""

    action: str  # "close_issue", "close_pr", "delete_branch", "delete_draft_pr"
    target: str  # description of what's being cleaned
    reason: str
    executed: bool = False
    error: str | None = None


@dataclass
class CleanupPlan:
    """All planned cleanup actions."""

    actions: list[CleanupAction] = field(default_factory=list)
    dry_run: bool = True

    @property
    def total(self) -> int:
        return len(self.actions)

    @property
    def executed_count(self) -> int:
        return sum(1 for a in self.actions if a.executed)

    @property
    def error_count(self) -> int:
        return sum(1 for a in self.actions if a.error)


def _run_gh(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a gh CLI command."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=_GH_TIMEOUT,
        cwd=cwd,
    )


def _run_gh_json(args: list[str], cwd: str | None = None) -> list | dict | None:
    """Run gh and parse JSON output."""
    try:
        result = _run_gh(args, cwd=cwd)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


class CleanupAgent:
    """Identifies and executes GitHub cleanup actions."""

    def __init__(
        self,
        cwd: str,
        stale_issue_days: int = 90,
        stale_pr_days: int = 30,
        delete_merged_branches: bool = True,
        close_draft_prs: bool = False,
        stale_label: str = "stale",
    ) -> None:
        self.cwd = cwd
        self.stale_issue_days = stale_issue_days
        self.stale_pr_days = stale_pr_days
        self.delete_merged_branches = delete_merged_branches
        self.close_draft_prs = close_draft_prs
        self.stale_label = stale_label

    def plan(self) -> CleanupPlan:
        """Build a cleanup plan without executing anything."""
        plan = CleanupPlan(dry_run=True)

        self._plan_stale_issues(plan)
        self._plan_stale_prs(plan)
        self._plan_draft_prs(plan)
        self._plan_merged_branches(plan)

        return plan

    def execute(self, plan: CleanupPlan) -> CleanupPlan:
        """Execute all actions in a plan."""
        plan.dry_run = False

        for action in plan.actions:
            try:
                self._execute_action(action)
                action.executed = True
            except Exception as exc:
                action.error = str(exc)
                logger.warning("Cleanup action failed: %s — %s", action.target, exc)

        return plan

    def _plan_stale_issues(self, plan: CleanupPlan) -> None:
        """Find issues not updated in stale_issue_days."""
        issues = _run_gh_json(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,updatedAt,labels",
                "--limit",
                "100",
            ],
            cwd=self.cwd,
        )
        if not isinstance(issues, list):
            return

        now = datetime.now(UTC)
        for issue in issues:
            updated = issue.get("updatedAt", "")
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_days = (now - updated_dt).days
            except (ValueError, TypeError):
                continue

            if age_days >= self.stale_issue_days:
                plan.actions.append(
                    CleanupAction(
                        action="close_issue",
                        target=f"#{issue['number']}: {issue.get('title', '')[:80]}",
                        reason=f"No activity for {age_days} days",
                    )
                )

    def _plan_stale_prs(self, plan: CleanupPlan) -> None:
        """Find PRs not updated in stale_pr_days."""
        prs = _run_gh_json(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,updatedAt,isDraft",
                "--limit",
                "100",
            ],
            cwd=self.cwd,
        )
        if not isinstance(prs, list):
            return

        now = datetime.now(UTC)
        for pr in prs:
            if pr.get("isDraft"):
                continue  # drafts handled by _plan_draft_prs

            updated = pr.get("updatedAt", "")
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_days = (now - updated_dt).days
            except (ValueError, TypeError):
                continue

            if age_days >= self.stale_pr_days:
                plan.actions.append(
                    CleanupAction(
                        action="close_pr",
                        target=f"PR #{pr['number']}: {pr.get('title', '')[:80]}",
                        reason=f"No activity for {age_days} days",
                    )
                )

    def _plan_draft_prs(self, plan: CleanupPlan) -> None:
        """Find abandoned draft PRs."""
        if not self.close_draft_prs:
            return

        prs = _run_gh_json(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,updatedAt,isDraft",
                "--limit",
                "100",
            ],
            cwd=self.cwd,
        )
        if not isinstance(prs, list):
            return

        now = datetime.now(UTC)
        for pr in prs:
            if not pr.get("isDraft"):
                continue

            updated = pr.get("updatedAt", "")
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_days = (now - updated_dt).days
            except (ValueError, TypeError):
                continue

            if age_days >= self.stale_pr_days:
                plan.actions.append(
                    CleanupAction(
                        action="close_pr",
                        target=f"Draft PR #{pr['number']}: {pr.get('title', '')[:80]}",
                        reason=f"Draft with no activity for {age_days} days",
                    )
                )

    def _plan_merged_branches(self, plan: CleanupPlan) -> None:
        """Find branches that have been merged but not deleted."""
        if not self.delete_merged_branches:
            return

        # Get merged PRs to find their head branches
        merged_prs = _run_gh_json(
            [
                "pr",
                "list",
                "--state",
                "merged",
                "--json",
                "number,headRefName,mergedAt",
                "--limit",
                "50",
            ],
            cwd=self.cwd,
        )
        if not isinstance(merged_prs, list):
            return

        # Get current remote branches
        try:
            result = subprocess.run(
                ["git", "branch", "-r", "--format", "%(refname:short)"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.cwd,
            )
            remote_branches = {
                b.replace("origin/", "")
                for b in result.stdout.strip().splitlines()
                if b.startswith("origin/")
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return

        # Protected branches to never delete
        protected = {"main", "master", "develop", "staging", "production"}

        for pr in merged_prs:
            branch = pr.get("headRefName", "")
            if branch and branch in remote_branches and branch not in protected:
                plan.actions.append(
                    CleanupAction(
                        action="delete_branch",
                        target=f"branch `{branch}` (merged in PR #{pr['number']})",
                        reason="Already merged",
                    )
                )

    def _execute_action(self, action: CleanupAction) -> None:
        """Execute a single cleanup action."""
        if action.action == "close_issue":
            number = action.target.split(":")[0].lstrip("#")
            result = _run_gh(
                [
                    "issue",
                    "close",
                    number,
                    "--comment",
                    f"Closing: {action.reason}. "
                    f"Labeled `{self.stale_label}`. Reopen if still relevant.",
                ],
                cwd=self.cwd,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

            # Add stale label
            _run_gh(
                ["issue", "edit", number, "--add-label", self.stale_label],
                cwd=self.cwd,
            )

        elif action.action == "close_pr":
            number = action.target.split("#")[1].split(":")[0]
            result = _run_gh(
                [
                    "pr",
                    "close",
                    number,
                    "--comment",
                    f"Closing: {action.reason}. Reopen if still needed.",
                ],
                cwd=self.cwd,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

        elif action.action == "delete_branch":
            # Extract branch name from target
            branch = action.target.split("`")[1]
            result = _run_gh(
                ["api", "-X", "DELETE", f"repos/{{owner}}/{{repo}}/git/refs/heads/{branch}"],
                cwd=self.cwd,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())
