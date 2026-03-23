"""Thin wrapper around anchormd generation logic for web use."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from anchormd.analyzers import run_all
from anchormd.generators.composer import DocumentComposer
from anchormd.models import ForgeConfig
from anchormd.scanner import CodebaseScanner

logger = logging.getLogger(__name__)

# Maximum clone time in seconds.
_CLONE_TIMEOUT = 60
# Maximum repo size we'll attempt (shallow clone mitigates this).
_MAX_SCAN_FILES = 5000


@dataclass
class GenerateResult:
    """Result of a CLAUDE.md generation run."""

    content: str
    score: int
    files_scanned: int
    languages: dict[str, int]
    error: str | None = None


def validate_github_url(url: str) -> str:
    """Validate and normalize a GitHub repo URL. Returns the normalized URL.

    Raises ValueError if the URL is not a valid public GitHub repo URL.
    """
    parsed = urlparse(url.strip())

    if parsed.scheme not in ("https", "http"):
        raise ValueError("URL must use https:// scheme")

    if parsed.hostname not in ("github.com", "www.github.com"):
        raise ValueError("Only github.com URLs are supported")

    # Extract owner/repo from path.
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError("URL must be in format: https://github.com/owner/repo")

    owner, repo = parts[0], parts[1]
    # Strip .git suffix if present.
    if repo.endswith(".git"):
        repo = repo[:-4]

    return f"https://github.com/{owner}/{repo}.git"


def clone_repo(url: str, dest: Path) -> None:
    """Shallow-clone a GitHub repo into dest.

    Raises RuntimeError on failure.
    """
    cmd = [
        "git",
        "clone",
        "--depth=1",
        "--single-branch",
        url,
        str(dest),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_CLONE_TIMEOUT,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "not found" in stderr.lower() or "404" in stderr:
                raise RuntimeError("Repository not found. Is it public?")
            raise RuntimeError(f"git clone failed: {stderr[:200]}")
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Clone timed out after {_CLONE_TIMEOUT}s. Repository may be too large."
        ) from exc


def generate_claude_md(repo_url: str) -> GenerateResult:
    """Clone a GitHub repo and generate a CLAUDE.md for it.

    This is the main entry point for the web API.
    """
    # Validate URL.
    try:
        normalized_url = validate_github_url(repo_url)
    except ValueError as exc:
        return GenerateResult(
            content="",
            score=0,
            files_scanned=0,
            languages={},
            error=str(exc),
        )

    tmp_dir = tempfile.mkdtemp(prefix="anchormd-scan-")
    clone_path = Path(tmp_dir) / "repo"

    try:
        # Clone.
        clone_repo(normalized_url, clone_path)

        # Configure and scan.
        config = ForgeConfig(root_path=clone_path, max_files=_MAX_SCAN_FILES)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()

        # Analyze.
        analyses = run_all(structure, config)

        # Compose.
        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses)
        score = composer.estimate_quality_score(content)

        return GenerateResult(
            content=content,
            score=score,
            files_scanned=structure.total_files,
            languages=structure.languages,
        )
    except RuntimeError as exc:
        return GenerateResult(
            content="",
            score=0,
            files_scanned=0,
            languages={},
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected error generating CLAUDE.md")
        return GenerateResult(
            content="",
            score=0,
            files_scanned=0,
            languages={},
            error=f"Generation failed: {type(exc).__name__}: {exc}",
        )
    finally:
        # Clean up cloned repo.
        shutil.rmtree(tmp_dir, ignore_errors=True)
