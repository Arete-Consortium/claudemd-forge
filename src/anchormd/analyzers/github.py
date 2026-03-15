"""GitHub repository health analyzer — uses gh CLI to gather repo metadata."""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
from datetime import UTC, datetime

from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)

_GH_TIMEOUT = 10


def _run_gh(args: list[str], cwd: str | None = None) -> dict | list | None:
    """Run a gh CLI command and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
            cwd=cwd,
        )
        if result.returncode != 0:
            logger.debug("gh %s failed: %s", " ".join(args), result.stderr.strip())
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.debug("gh command error: %s", exc)
        return None


def _run_gh_text(args: list[str], cwd: str | None = None) -> str | None:
    """Run a gh CLI command and return raw text output."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
            cwd=cwd,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


class GitHubAnalyzer:
    """Analyzes GitHub repository health via the gh CLI."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Gather GitHub repo metadata and produce health findings."""
        cwd = str(structure.root)
        findings: dict[str, object] = {}

        # Check if we're in a gh-authenticated repo
        repo_json = _run_gh(
            [
                "repo",
                "view",
                "--json",
                "name,owner,defaultBranchRef,isPrivate,description,"
                "stargazerCount,forkCount,hasIssuesEnabled,hasWikiEnabled,"
                "licenseInfo,pushedAt,createdAt",
            ],
            cwd=cwd,
        )

        if repo_json is None or not isinstance(repo_json, dict):
            return AnalysisResult(
                category="github",
                findings={
                    "available": False,
                    "reason": "Not a GitHub repo or gh not authenticated",
                },
                confidence=0.0,
                section_content="",
            )

        findings["available"] = True
        owner = (repo_json.get("owner") or {}).get("login", "")
        findings["repo"] = f"{owner}/{repo_json.get('name', '')}"
        findings["private"] = repo_json.get("isPrivate", False)
        findings["stars"] = repo_json.get("stargazerCount", 0)
        findings["forks"] = repo_json.get("forkCount", 0)
        findings["default_branch"] = (repo_json.get("defaultBranchRef", {}) or {}).get(
            "name", "main"
        )
        findings["license"] = (repo_json.get("licenseInfo", {}) or {}).get("name")
        findings["last_push"] = repo_json.get("pushedAt")

        # Issues
        issues = self._get_issues(cwd)
        findings["issues"] = issues

        # PRs
        prs = self._get_pull_requests(cwd)
        findings["pull_requests"] = prs

        # Security alerts
        security = self._get_security(cwd)
        findings["security"] = security

        # Branch protection
        default_branch = findings["default_branch"]
        protection = self._get_branch_protection(cwd, default_branch)
        findings["branch_protection"] = protection

        # Recent releases
        releases = self._get_releases(cwd)
        findings["releases"] = releases

        # CI workflows
        workflows = self._get_workflows(cwd)
        findings["workflows"] = workflows

        # Calculate health score
        findings["health_score"] = self._calculate_health(findings)

        confidence = 0.9
        section = self._render_section(findings)

        return AnalysisResult(
            category="github",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _get_issues(self, cwd: str) -> dict:
        """Get issue counts and staleness."""
        result: dict[str, object] = {"open": 0, "stale_30d": 0, "stale_90d": 0}

        issues = _run_gh(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,createdAt,updatedAt,labels",
                "--limit",
                "100",
            ],
            cwd=cwd,
        )
        if not isinstance(issues, list):
            return result

        now = datetime.now(UTC)
        result["open"] = len(issues)

        stale_30 = 0
        stale_90 = 0
        for issue in issues:
            updated = issue.get("updatedAt", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    age_days = (now - updated_dt).days
                    if age_days > 90:
                        stale_90 += 1
                    elif age_days > 30:
                        stale_30 += 1
                except (ValueError, TypeError):
                    pass

        result["stale_30d"] = stale_30
        result["stale_90d"] = stale_90
        return result

    def _get_pull_requests(self, cwd: str) -> dict:
        """Get PR counts and staleness."""
        result: dict[str, object] = {"open": 0, "draft": 0, "stale_30d": 0}

        prs = _run_gh(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,createdAt,updatedAt,isDraft",
                "--limit",
                "100",
            ],
            cwd=cwd,
        )
        if not isinstance(prs, list):
            return result

        now = datetime.now(UTC)
        result["open"] = len(prs)
        result["draft"] = sum(1 for pr in prs if pr.get("isDraft"))

        stale = 0
        for pr in prs:
            updated = pr.get("updatedAt", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if (now - updated_dt).days > 30:
                        stale += 1
                except (ValueError, TypeError):
                    pass

        result["stale_30d"] = stale
        return result

    def _get_security(self, cwd: str) -> dict:
        """Get security alert counts."""
        result: dict[str, int] = {"dependabot_alerts": 0, "code_scanning_alerts": 0}

        # Dependabot alerts
        alerts = _run_gh(
            ["api", "repos/{owner}/{repo}/dependabot/alerts", "--jq", "length"],
            cwd=cwd,
        )
        if alerts is not None:
            with contextlib.suppress(ValueError, TypeError):
                result["dependabot_alerts"] = int(alerts)

        # Code scanning
        scanning = _run_gh(
            ["api", "repos/{owner}/{repo}/code-scanning/alerts", "--jq", "length"],
            cwd=cwd,
        )
        if scanning is not None:
            with contextlib.suppress(ValueError, TypeError):
                result["code_scanning_alerts"] = int(scanning)

        return result

    def _get_branch_protection(self, cwd: str, branch: str) -> dict:
        """Check if the default branch has protection rules."""
        result: dict[str, object] = {"enabled": False}

        protection = _run_gh(
            ["api", f"repos/{{owner}}/{{repo}}/branches/{branch}/protection"],
            cwd=cwd,
        )
        if isinstance(protection, dict) and "url" in protection:
            result["enabled"] = True
            result["require_reviews"] = bool(protection.get("required_pull_request_reviews"))
            result["require_status_checks"] = bool(protection.get("required_status_checks"))
            result["enforce_admins"] = (protection.get("enforce_admins", {}) or {}).get(
                "enabled", False
            )

        return result

    def _get_releases(self, cwd: str) -> dict:
        """Get recent release info."""
        result: dict[str, object] = {"total": 0, "latest": None, "latest_date": None}

        releases = _run_gh(
            ["release", "list", "--json", "tagName,publishedAt,isPrerelease", "--limit", "10"],
            cwd=cwd,
        )
        if not isinstance(releases, list):
            return result

        result["total"] = len(releases)
        if releases:
            latest = releases[0]
            result["latest"] = latest.get("tagName")
            result["latest_date"] = latest.get("publishedAt")

        return result

    def _get_workflows(self, cwd: str) -> dict:
        """Get CI workflow status."""
        result: dict[str, object] = {"count": 0, "failing": []}

        runs = _run_gh(
            ["run", "list", "--json", "workflowName,status,conclusion", "--limit", "20"],
            cwd=cwd,
        )
        if not isinstance(runs, list):
            return result

        # Get unique workflow names and their latest status
        seen: dict[str, str] = {}
        for run in runs:
            name = run.get("workflowName", "unknown")
            if name not in seen:
                seen[name] = run.get("conclusion", run.get("status", "unknown"))

        result["count"] = len(seen)
        result["failing"] = [name for name, conclusion in seen.items() if conclusion == "failure"]
        return result

    def _calculate_health(self, findings: dict) -> int:
        """Calculate 0-100 GitHub health score."""
        score = 100

        # Security alerts
        security = findings.get("security", {})
        score -= min(30, security.get("dependabot_alerts", 0) * 5)
        score -= min(30, security.get("code_scanning_alerts", 0) * 10)

        # Stale issues
        issues = findings.get("issues", {})
        score -= min(10, issues.get("stale_90d", 0) * 2)
        score -= min(5, issues.get("stale_30d", 0))

        # Stale PRs
        prs = findings.get("pull_requests", {})
        score -= min(10, prs.get("stale_30d", 0) * 3)

        # No branch protection
        protection = findings.get("branch_protection", {})
        if not protection.get("enabled"):
            score -= 10

        # Failing CI
        workflows = findings.get("workflows", {})
        failing = workflows.get("failing", [])
        score -= min(15, len(failing) * 5)

        # No license
        if not findings.get("license"):
            score -= 5

        return max(0, min(100, score))

    def _render_section(self, findings: dict) -> str:
        """Render GitHub health section for context file."""
        if not findings.get("available"):
            return ""

        lines: list[str] = ["## GitHub Health", ""]

        health = findings.get("health_score", 0)
        lines.append(f"**Health Score**: {health}/100")
        lines.append(f"**Repository**: {findings.get('repo', 'unknown')}")
        lines.append("")

        # Security
        security = findings.get("security", {})
        dep_alerts = security.get("dependabot_alerts", 0)
        scan_alerts = security.get("code_scanning_alerts", 0)
        if dep_alerts or scan_alerts:
            lines.append("### Security Alerts")
            if dep_alerts:
                lines.append(f"- **Dependabot**: {dep_alerts} open alerts")
            if scan_alerts:
                lines.append(f"- **Code Scanning**: {scan_alerts} open alerts")
            lines.append("")

        # Issues & PRs
        issues = findings.get("issues", {})
        prs = findings.get("pull_requests", {})
        lines.append("### Activity")
        lines.append(f"- **Open Issues**: {issues.get('open', 0)}")
        if issues.get("stale_90d"):
            lines.append(f"  - Stale (>90 days): {issues['stale_90d']}")
        lines.append(f"- **Open PRs**: {prs.get('open', 0)}")
        if prs.get("draft"):
            lines.append(f"  - Draft: {prs['draft']}")
        if prs.get("stale_30d"):
            lines.append(f"  - Stale (>30 days): {prs['stale_30d']}")
        lines.append("")

        # CI
        workflows = findings.get("workflows", {})
        if workflows.get("count"):
            failing = workflows.get("failing", [])
            if failing:
                lines.append("### CI Status")
                for wf in failing:
                    lines.append(f"- **FAILING**: {wf}")
                lines.append("")

        # Protection
        protection = findings.get("branch_protection", {})
        if not protection.get("enabled"):
            lines.append(
                f"**Warning**: Default branch `{findings.get('default_branch', 'main')}` "
                f"has no branch protection rules."
            )
            lines.append("")

        # Releases
        releases = findings.get("releases", {})
        if releases.get("latest"):
            lines.append(f"**Latest Release**: {releases['latest']}")
            lines.append("")

        return "\n".join(lines)
