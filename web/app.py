"""FastAPI web application for anchormd — GitHub URL in, CLAUDE.md out."""

from __future__ import annotations

import asyncio
import hashlib
import json as json_module
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import stripe
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.generator import generate_claude_md

logger = logging.getLogger(__name__)

# --- Configuration ---

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
ADMIN_GITHUB_USERNAME = os.environ.get("ADMIN_GITHUB_USERNAME", "AreteDriver")

# Stripe configuration.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
DEEP_SCAN_PRICE_CENTS = 2900  # $29.00 one-time
SITE_URL = os.environ.get("SITE_URL", "https://anchormd.dev")
LICENSE_SERVER_URL = os.environ.get("ANCHORMD_LICENSE_SERVER", "")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Database path — configurable via env but defaults to local.
DB_PATH = Path(__file__).parent / "scans.db"

# Static files path (built React frontend).
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"

# Concurrency limit for batch scans.
_BATCH_CONCURRENCY = 3


def _get_db() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_db() -> None:
    """Create all tables if they don't exist, and migrate existing ones."""
    conn = _get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                repo_url TEXT NOT NULL,
                content TEXT,
                score INTEGER,
                files_scanned INTEGER DEFAULT 0,
                languages TEXT DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                user_id INTEGER,
                batch_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                github_id INTEGER UNIQUE,
                username TEXT,
                avatar_url TEXT,
                access_token TEXT,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_batches (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                repo_count INTEGER,
                completed INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        # Migrate: add columns to scans if missing.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(scans)").fetchall()}
        if "user_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER")
        if "batch_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN batch_id TEXT")
        if "scan_type" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN scan_type TEXT DEFAULT 'free'")
        if "recommendations" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN recommendations TEXT")
        if "stripe_session_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN stripe_session_id TEXT")
        if "email" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN email TEXT")
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # noqa: ANN401
    """Initialize database on startup."""
    _init_db()
    yield


app = FastAPI(
    title="anchormd",
    description="Generate CLAUDE.md files from GitHub repos",
    version="0.2.0",
    lifespan=lifespan,
)


# --- Models ---


class ScanRequest(BaseModel):
    """Request body for POST /api/scan."""

    repo_url: str = Field(..., description="GitHub repository URL")


class ScanAllRequest(BaseModel):
    """Request body for POST /api/scan-all."""

    username: str = Field(..., description="GitHub username")


class ScanResponse(BaseModel):
    """Response for a scan result."""

    scan_id: str
    repo_url: str
    content: str | None = None
    score: int | None = None
    files_scanned: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    status: str = "pending"
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    batch_id: str | None = None
    scan_type: str = "free"


class BatchStatusResponse(BaseModel):
    """Response for scan batch status."""

    batch_id: str
    repo_count: int
    completed: int
    scans: list[dict[str, Any]]


class RepoInfo(BaseModel):
    """GitHub repository info."""

    name: str
    full_name: str
    private: bool
    language: str | None = None
    stargazers_count: int = 0
    updated_at: str | None = None
    html_url: str


class CheckoutRequest(BaseModel):
    """Request body for POST /api/checkout/deep-scan."""

    repo_url: str = Field(..., description="GitHub repository URL")
    email: str = Field(..., description="Email for receipt delivery")


class CheckoutResponse(BaseModel):
    """Response for checkout session creation."""

    checkout_url: str
    scan_id: str


class DeepScanReport(BaseModel):
    """Deep scan report response."""

    scan_id: str
    repo_url: str
    content: str | None = None
    score: int | None = None
    files_scanned: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    scan_type: str = "deep"
    status: str = "pending"
    created_at: str | None = None
    completed_at: str | None = None


class AdminMetrics(BaseModel):
    """Admin dashboard metrics."""

    total_scans: int
    unique_users: int
    scans_by_day: list[dict[str, Any]]
    most_scanned_repos: list[dict[str, Any]]
    average_score: float
    error_rate: float
    recent_scans: list[dict[str, Any]]


# --- Auth Helpers ---


async def _get_current_user(request: Request) -> dict[str, Any] | None:
    """Extract user from Authorization header. Returns None if not authenticated."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE access_token = ?", (token,)).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


async def _require_user(request: Request) -> dict[str, Any]:
    """Require authenticated user. Raises 401 if not authenticated."""
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def _require_admin(request: Request) -> dict[str, Any]:
    """Require admin user. Raises 403 if not admin."""
    user = await _require_user(request)
    if user.get("username") != ADMIN_GITHUB_USERNAME:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# --- Helpers ---


def _make_scan_id(repo_url: str) -> str:
    """Generate a deterministic scan ID from URL + timestamp."""
    raw = f"{repo_url}:{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _run_scan(
    scan_id: str,
    repo_url: str,
    token: str | None = None,
    batch_id: str | None = None,
) -> None:
    """Execute the scan in a background thread."""
    import json

    result = generate_claude_md(repo_url, token=token)

    conn = _get_db()
    try:
        now = datetime.now(UTC).isoformat()
        if result.error:
            conn.execute(
                """
                UPDATE scans SET status = 'error', error = ?, completed_at = ?
                WHERE scan_id = ?
                """,
                (result.error, now, scan_id),
            )
        else:
            conn.execute(
                """
                UPDATE scans
                SET status = 'complete', content = ?, score = ?,
                    files_scanned = ?, languages = ?, completed_at = ?
                WHERE scan_id = ?
                """,
                (
                    result.content,
                    result.score,
                    result.files_scanned,
                    json.dumps(result.languages),
                    now,
                    scan_id,
                ),
            )
        # Update batch completed count if part of a batch.
        if batch_id:
            conn.execute(
                "UPDATE scan_batches SET completed = completed + 1 WHERE id = ?",
                (batch_id,),
            )
        conn.commit()
    except Exception:
        logger.exception("Failed to update scan %s", scan_id)
    finally:
        conn.close()


async def _fetch_all_repos(token: str) -> list[dict[str, Any]]:
    """Fetch all repos for the authenticated user, paginating through all pages."""
    repos: list[dict[str, Any]] = []
    page = 1
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={
                    "per_page": 100,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                    "affiliation": "owner,organization_member",
                },
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1
    return repos


# --- API Routes: Auth ---


@app.get("/api/auth/github")
async def github_login() -> dict[str, str]:
    """Return the GitHub OAuth authorize URL."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI", "https://anchormd.dev/")
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo,read:user"
    )
    return {"url": url}


@app.get("/api/auth/callback")
async def github_callback(code: str) -> dict[str, Any]:
    """Exchange GitHub OAuth code for access token and upsert user."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Exchange code for token.
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to exchange code")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error_desc = token_data.get("error_description", "Unknown error")
            raise HTTPException(status_code=400, detail=f"OAuth error: {error_desc}")

        # Fetch user info.
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch user info")

        user_data = user_resp.json()

    # Upsert user in database.
    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO users (github_id, username, avatar_url, access_token, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(github_id) DO UPDATE SET
                username = excluded.username,
                avatar_url = excluded.avatar_url,
                access_token = excluded.access_token
            """,
            (
                user_data["id"],
                user_data["login"],
                user_data.get("avatar_url", ""),
                access_token,
                time.time(),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE github_id = ?", (user_data["id"],)).fetchone()
        user_id = dict(row)["id"] if row else None
    finally:
        conn.close()

    return {
        "token": access_token,
        "user": {
            "id": user_id,
            "github_id": user_data["id"],
            "username": user_data["login"],
            "avatar_url": user_data.get("avatar_url", ""),
            "is_admin": user_data["login"] == ADMIN_GITHUB_USERNAME,
        },
    }


@app.get("/api/auth/me")
async def get_me(user: dict[str, Any] = Depends(_require_user)) -> dict[str, Any]:
    """Return the current authenticated user."""
    return {
        "id": user["id"],
        "github_id": user["github_id"],
        "username": user["username"],
        "avatar_url": user["avatar_url"],
        "is_admin": user["username"] == ADMIN_GITHUB_USERNAME,
    }


# --- API Routes: Repos ---


@app.get("/api/repos")
async def list_repos(
    user: dict[str, Any] = Depends(_require_user),
) -> list[dict[str, Any]]:
    """List all repos for the authenticated user."""
    token = user["access_token"]
    raw_repos = await _fetch_all_repos(token)

    return [
        {
            "name": r["name"],
            "full_name": r["full_name"],
            "private": r["private"],
            "language": r.get("language"),
            "stargazers_count": r.get("stargazers_count", 0),
            "updated_at": r.get("updated_at"),
            "pushed_at": r.get("pushed_at"),
            "html_url": r["html_url"],
        }
        for r in raw_repos
    ]


# --- Quota Helpers ---


async def _check_web_quota(
    scan_type: str, license_key: str | None = None, repo_fingerprint: str | None = None
) -> dict | None:
    """Check scan quota against the license server. Returns usage dict or None."""
    if not LICENSE_SERVER_URL:
        return None  # No server = no enforcement
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LICENSE_SERVER_URL}/v1/usage/check",
                json={
                    "license_key": license_key or "",
                    "scan_type": scan_type,
                },
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        logger.debug("Quota check failed", exc_info=True)
    return None


async def _record_web_usage(
    scan_type: str, license_key: str | None = None, repo_fingerprint: str | None = None
) -> None:
    """Record a scan against the license server. Fire-and-forget."""
    if not LICENSE_SERVER_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{LICENSE_SERVER_URL}/v1/usage",
                json={
                    "license_key": license_key or "",
                    "scan_type": scan_type,
                    "repo_fingerprint": repo_fingerprint,
                },
                timeout=5.0,
            )
    except Exception:
        logger.debug("Usage record failed", exc_info=True)


def _repo_fingerprint(repo_url: str) -> str:
    """Generate a stable fingerprint for a repo URL."""
    return hashlib.sha256(repo_url.lower().strip().encode()).hexdigest()[:16]


# --- Free Scan Caching ---


def _get_cached_free_scan(repo_url: str) -> dict | None:
    """Return a cached free scan for a repo if one exists and completed."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT scan_id, status, content, score FROM scans "
            "WHERE repo_url = ? AND scan_type = 'free' AND status = 'complete' "
            "ORDER BY created_at DESC LIMIT 1",
            (repo_url,),
        ).fetchone()
        if row:
            return {"scan_id": row["scan_id"], "status": row["status"], "cached": True}
    finally:
        conn.close()
    return None


# --- API Routes: Scan ---


@app.post("/api/scan", response_model=ScanResponse)
async def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    req: Request,
) -> ScanResponse:
    """Accept a GitHub repo URL and start generating a CLAUDE.md."""
    user = await _get_current_user(req)
    user_id = user["id"] if user else None
    token = user["access_token"] if user else None

    # Return cached result for repeat free scans of the same repo
    cached = _get_cached_free_scan(request.repo_url)
    if cached:
        return ScanResponse(
            scan_id=cached["scan_id"],
            repo_url=request.repo_url,
            status="complete",
            created_at="",
        )

    scan_id = _make_scan_id(request.repo_url)
    now = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO scans (scan_id, repo_url, status, created_at, user_id)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (scan_id, request.repo_url, now, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    background_tasks.add_task(_run_scan, scan_id, request.repo_url, token)

    return ScanResponse(
        scan_id=scan_id,
        repo_url=request.repo_url,
        status="pending",
        created_at=now,
    )


@app.get("/api/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    """Retrieve a previous scan result."""
    import json

    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = dict(row)
    languages_raw = row_dict.get("languages", "{}")
    try:
        languages = json.loads(languages_raw) if languages_raw else {}
    except (json.JSONDecodeError, TypeError):
        languages = {}

    return ScanResponse(
        scan_id=row_dict["scan_id"],
        repo_url=row_dict["repo_url"],
        content=row_dict.get("content"),
        score=row_dict.get("score"),
        files_scanned=row_dict.get("files_scanned", 0),
        languages=languages,
        status=row_dict["status"],
        error=row_dict.get("error"),
        created_at=row_dict.get("created_at"),
        completed_at=row_dict.get("completed_at"),
        batch_id=row_dict.get("batch_id"),
        scan_type=row_dict.get("scan_type", "free"),
    )


# --- API Routes: Batch Scan ---


@app.post("/api/scan-all")
async def scan_all(
    request: ScanAllRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Queue scans for all repos belonging to the authenticated user.

    Repos with a previous score of 100 that haven't been pushed to since the
    last scan are skipped and their cached result is reused.
    """
    import json as _json

    token = user["access_token"]
    repos = await _fetch_all_repos(token)

    if not repos:
        raise HTTPException(status_code=404, detail="No repos found")

    batch_id = uuid.uuid4().hex[:12]
    now_ts = time.time()
    now_iso = datetime.now(UTC).isoformat()

    # Look up previous best scan per repo URL to detect cacheable 100s.
    conn = _get_db()
    try:
        # Get the most recent complete scan per repo_url for this user.
        cached_rows = conn.execute(
            """
            SELECT repo_url, scan_id, score, content, files_scanned, languages,
                   completed_at
            FROM scans
            WHERE user_id = ? AND status = 'complete' AND score = 100
            ORDER BY completed_at DESC
            """,
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()

    # Build lookup: repo_url -> best cached scan (first seen = most recent).
    cached_by_url: dict[str, dict[str, Any]] = {}
    for row in cached_rows:
        rd = dict(row)
        if rd["repo_url"] not in cached_by_url:
            cached_by_url[rd["repo_url"]] = rd

    # Partition repos into skip (cached 100, no new pushes) vs scan.
    to_scan: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for repo in repos:
        url = repo["html_url"]
        cached = cached_by_url.get(url)
        if cached and cached.get("completed_at"):
            pushed_at = repo.get("pushed_at", "")
            completed_at = cached["completed_at"]
            # Both are ISO 8601 strings — lexicographic comparison works.
            if pushed_at and completed_at and pushed_at <= completed_at:
                skipped.append(repo)
                continue
        to_scan.append(repo)

    # Total count includes skipped (they appear as instant completions).
    total_count = len(repos)
    skipped_count = len(skipped)

    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO scan_batches (id, user_id, repo_count, completed, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (batch_id, user["id"], total_count, skipped_count, now_ts),
        )

        # Insert cached results as already-complete scans.
        for repo in skipped:
            url = repo["html_url"]
            cached = cached_by_url[url]
            scan_id = _make_scan_id(url)
            conn.execute(
                """
                INSERT INTO scans (scan_id, repo_url, status, score, content,
                    files_scanned, languages, created_at, completed_at,
                    user_id, batch_id)
                VALUES (?, ?, 'complete', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id, url, cached["score"], cached["content"],
                    cached["files_scanned"], cached["languages"],
                    now_iso, now_iso, user["id"], batch_id,
                ),
            )

        # Insert pending scans for repos that need re-scanning.
        scan_ids = []
        for repo in to_scan:
            scan_id = _make_scan_id(repo["html_url"])
            scan_ids.append(scan_id)
            conn.execute(
                """
                INSERT INTO scans (scan_id, repo_url, status, created_at, user_id, batch_id)
                VALUES (?, ?, 'pending', ?, ?, ?)
                """,
                (scan_id, repo["html_url"], now_iso, user["id"], batch_id),
            )
        conn.commit()
    finally:
        conn.close()

    # Run batch scans with concurrency limit in background.
    async def _run_batch() -> None:
        sem = asyncio.Semaphore(_BATCH_CONCURRENCY)

        async def _scan_one(sid: str, url: str) -> None:
            async with sem:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _run_scan, sid, url, token, batch_id)

        tasks = [
            _scan_one(sid, repo["html_url"]) for sid, repo in zip(scan_ids, to_scan, strict=True)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    if to_scan:
        background_tasks.add_task(_run_batch)

    return {
        "batch_id": batch_id,
        "repo_count": total_count,
        "skipped": skipped_count,
        "scanning": len(to_scan),
    }


@app.get("/api/scan-batch/{batch_id}")
async def get_batch_status(batch_id: str) -> BatchStatusResponse:
    """Return the status of all scans in a batch."""
    conn = _get_db()
    try:
        batch_row = conn.execute("SELECT * FROM scan_batches WHERE id = ?", (batch_id,)).fetchone()
        if not batch_row:
            raise HTTPException(status_code=404, detail="Batch not found")

        batch_dict = dict(batch_row)
        scan_rows = conn.execute(
            "SELECT scan_id, repo_url, status, score, error FROM scans WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
    finally:
        conn.close()

    return BatchStatusResponse(
        batch_id=batch_id,
        repo_count=batch_dict["repo_count"],
        completed=batch_dict["completed"],
        scans=[dict(r) for r in scan_rows],
    )


# --- Deep Scan Logic ---


def _generate_recommendations(content: str, score: int) -> list[dict[str, Any]]:
    """Generate architecture recommendations based on scan results."""
    recommendations: list[dict[str, Any]] = []

    checks = [
        (
            "## Anti-Patterns" not in content,
            "high",
            "Add Anti-Patterns Section",
            "Define explicit anti-patterns to prevent common mistakes. "
            "Include rules like no bare except, no mutable defaults, no print debugging.",
        ),
        (
            "## Testing" not in content and "test" not in content.lower(),
            "high",
            "Add Testing Standards",
            "Document test frameworks, coverage targets, and testing conventions. "
            "AI agents write better tests when standards are explicit.",
        ),
        (
            "## Environment" not in content and "env" not in content.lower(),
            "medium",
            "Document Environment Variables",
            "List required environment variables with descriptions. "
            "Prevents accidental credential exposure and misconfiguration.",
        ),
        (
            "## Architecture" not in content,
            "medium",
            "Add Architecture Overview",
            "Include a directory tree and component descriptions. "
            "Helps AI agents understand project structure without exploring.",
        ),
        (
            "## Dependencies" not in content,
            "low",
            "Document Dependencies",
            "List key dependencies and their purposes. "
            "Prevents AI agents from introducing conflicting packages.",
        ),
        (
            "## CI/CD" not in content and "workflow" not in content.lower(),
            "medium",
            "Add CI/CD Documentation",
            "Document build, test, and deploy workflows. "
            "AI agents can then update CI configs correctly.",
        ),
        (
            "## Security" not in content,
            "high",
            "Add Security Guidelines",
            "Document credential handling, input validation, and security policies. "
            "Critical for preventing AI-generated security vulnerabilities.",
        ),
        (
            score < 60,
            "high",
            "Improve Overall Coverage",
            f"Current score is {score}/100. Focus on adding missing sections "
            "to give AI agents comprehensive context about your codebase.",
        ),
    ]

    for condition, priority, title, description in checks:
        if condition:
            recommendations.append(
                {"priority": priority, "title": title, "description": description}
            )

    return recommendations


def _run_deep_scan(scan_id: str, repo_url: str) -> None:
    """Execute a deep scan (same generation + recommendations)."""
    result = generate_claude_md(repo_url)

    conn = _get_db()
    try:
        now = datetime.now(UTC).isoformat()
        if result.error:
            conn.execute(
                """
                UPDATE scans SET status = 'error', error = ?, completed_at = ?
                WHERE scan_id = ?
                """,
                (result.error, now, scan_id),
            )
        else:
            recs = _generate_recommendations(result.content, result.score)
            conn.execute(
                """
                UPDATE scans
                SET status = 'complete', content = ?, score = ?,
                    files_scanned = ?, languages = ?, completed_at = ?,
                    recommendations = ?
                WHERE scan_id = ?
                """,
                (
                    result.content,
                    result.score,
                    result.files_scanned,
                    json_module.dumps(result.languages),
                    now,
                    json_module.dumps(recs),
                    scan_id,
                ),
            )
        conn.commit()
    except Exception:
        logger.exception("Failed to update deep scan %s", scan_id)
    finally:
        conn.close()


# --- API Routes: Stripe Checkout ---


@app.post("/api/checkout/deep-scan", response_model=CheckoutResponse)
async def create_deep_scan_checkout(request: CheckoutRequest) -> CheckoutResponse:
    """Create a Stripe Checkout session for a $29 deep scan."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    # Pre-create the scan record so we have an ID for the success URL.
    scan_id = _make_scan_id(request.repo_url)
    now = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO scans (scan_id, repo_url, status, created_at, scan_type, email)
            VALUES (?, ?, 'awaiting_payment', ?, 'deep', ?)
            """,
            (scan_id, request.repo_url, now, request.email),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "anchormd Deep Scan",
                            "description": (
                                "Full audit report with architecture recommendations "
                                "for your repository."
                            ),
                        },
                        "unit_amount": DEEP_SCAN_PRICE_CENTS,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            customer_email=request.email,
            success_url=f"{SITE_URL}/?deep_scan={scan_id}",
            cancel_url=f"{SITE_URL}/",
            metadata={
                "product": "deep_scan",
                "repo_url": request.repo_url,
                "scan_id": scan_id,
            },
        )
    except stripe.StripeError as exc:
        logger.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service error") from exc

    # Store stripe session ID.
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE scans SET stripe_session_id = ? WHERE scan_id = ?",
            (session.id, scan_id),
        )
        conn.commit()
    finally:
        conn.close()

    return CheckoutResponse(checkout_url=session.url, scan_id=scan_id)


# --- API Routes: Stripe Webhook ---


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Handle Stripe webhook events (checkout.session.completed)."""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})

        if metadata.get("product") == "deep_scan":
            scan_id = metadata.get("scan_id")
            repo_url = metadata.get("repo_url")

            if scan_id and repo_url:
                # Update status to pending (payment confirmed, scan starting).
                conn = _get_db()
                try:
                    conn.execute(
                        "UPDATE scans SET status = 'pending' WHERE scan_id = ?",
                        (scan_id,),
                    )
                    conn.commit()
                finally:
                    conn.close()

                # Trigger deep scan in background.
                background_tasks.add_task(_run_deep_scan, scan_id, repo_url)

                # Record usage against license server (fire-and-forget)
                email = session.get("customer_email", "")
                background_tasks.add_task(
                    _record_web_usage, "deep_scan", email, _repo_fingerprint(repo_url)
                )

    return {"status": "ok"}


# --- API Routes: Deep Scan Report ---


@app.get("/api/scan/{scan_id}/report", response_model=DeepScanReport)
async def get_deep_scan_report(scan_id: str) -> DeepScanReport:
    """Retrieve a deep scan report. Only available for paid deep scans."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = dict(row)

    if row_dict.get("scan_type") != "deep":
        raise HTTPException(status_code=403, detail="Deep scan report requires payment")

    languages_raw = row_dict.get("languages", "{}")
    try:
        languages = json_module.loads(languages_raw) if languages_raw else {}
    except (json_module.JSONDecodeError, TypeError):
        languages = {}

    recs_raw = row_dict.get("recommendations", "[]")
    try:
        recommendations = json_module.loads(recs_raw) if recs_raw else []
    except (json_module.JSONDecodeError, TypeError):
        recommendations = []

    return DeepScanReport(
        scan_id=row_dict["scan_id"],
        repo_url=row_dict["repo_url"],
        content=row_dict.get("content"),
        score=row_dict.get("score"),
        files_scanned=row_dict.get("files_scanned", 0),
        languages=languages,
        recommendations=recommendations,
        scan_type="deep",
        status=row_dict["status"],
        created_at=row_dict.get("created_at"),
        completed_at=row_dict.get("completed_at"),
    )


# --- API Routes: Push PR ---


class PushPRRequest(BaseModel):
    """Request body for POST /api/scan/{scan_id}/push-pr."""

    branch_name: str = Field(default="anchormd/claude-md", description="Branch name for the PR")
    commit_message: str = Field(
        default="docs: add CLAUDE.md generated by anchormd",
        description="Commit message",
    )


class PushPRResponse(BaseModel):
    """Response for push-pr endpoint."""

    pr_url: str
    branch: str
    status: str = "created"


@app.post("/api/scan/{scan_id}/push-pr")
async def push_pr(
    scan_id: str,
    request: PushPRRequest,
    user: dict[str, Any] = Depends(_require_user),
) -> PushPRResponse:
    """Create a PR that adds/updates CLAUDE.md in the scanned repo."""
    import base64

    # Get the scan result.
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = dict(row)
    if row_dict["status"] != "complete" or not row_dict.get("content"):
        raise HTTPException(status_code=400, detail="Scan not complete or has no content")

    content = row_dict["content"]
    repo_url = row_dict["repo_url"]

    # Parse owner/repo from URL.
    parts = [p for p in repo_url.rstrip("/").split("/") if p]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Cannot parse repo from URL")
    owner = parts[-2]
    repo = parts[-1].replace(".git", "")

    token = user["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # 1. Get default branch and its HEAD SHA.
        repo_resp = await client.get(api_base)
        if repo_resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot access repo: {repo_resp.status_code}",
            )
        repo_data = repo_resp.json()
        default_branch = repo_data["default_branch"]

        ref_resp = await client.get(f"{api_base}/git/ref/heads/{default_branch}")
        if ref_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Cannot get default branch ref")
        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create branch (or update if exists).
        branch = request.branch_name
        create_ref = await client.post(
            f"{api_base}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        if create_ref.status_code == 422:
            # Branch exists — update it to latest default branch.
            await client.patch(
                f"{api_base}/git/refs/heads/{branch}",
                json={"sha": base_sha, "force": True},
            )

        # 3. Create or update CLAUDE.md via Contents API.
        # Check if file exists on the branch to get its SHA for updates.
        existing = await client.get(
            f"{api_base}/contents/CLAUDE.md",
            params={"ref": branch},
        )
        file_payload: dict[str, Any] = {
            "message": request.commit_message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if existing.status_code == 200:
            file_payload["sha"] = existing.json()["sha"]

        put_resp = await client.put(
            f"{api_base}/contents/CLAUDE.md",
            json=file_payload,
        )
        if put_resp.status_code not in (200, 201):
            detail = put_resp.json().get("message", "Unknown error")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create file: {detail}",
            )

        # 4. Create PR.
        pr_body = (
            "## CLAUDE.md generated by anchormd\n\n"
            f"**Score:** {row_dict.get('score', 'N/A')}/100\n"
            f"**Files scanned:** {row_dict.get('files_scanned', 0)}\n\n"
            "This PR adds a `CLAUDE.md` file generated by "
            "[anchormd](https://anchormd.dev) — giving AI coding agents "
            "(Claude Code, Cursor, Copilot) accurate context about your project.\n\n"
            "Review the file and merge when ready."
        )

        pr_resp = await client.post(
            f"{api_base}/pulls",
            json={
                "title": "Add CLAUDE.md for AI coding agents",
                "body": pr_body,
                "head": branch,
                "base": default_branch,
            },
        )

        if pr_resp.status_code == 201:
            pr_url = pr_resp.json()["html_url"]
            return PushPRResponse(pr_url=pr_url, branch=branch, status="created")
        elif pr_resp.status_code == 422:
            # PR already exists — find it.
            prs_resp = await client.get(
                f"{api_base}/pulls",
                params={"head": f"{owner}:{branch}", "state": "open"},
            )
            if prs_resp.status_code == 200 and prs_resp.json():
                pr_url = prs_resp.json()[0]["html_url"]
                return PushPRResponse(pr_url=pr_url, branch=branch, status="updated")
            raise HTTPException(status_code=400, detail="PR exists but could not be found")
        else:
            detail = pr_resp.json().get("message", "Unknown error")
            raise HTTPException(status_code=400, detail=f"Failed to create PR: {detail}")


# --- API Routes: Admin ---


@app.get("/api/admin/metrics")
async def admin_metrics(
    user: dict[str, Any] = Depends(_require_admin),
) -> AdminMetrics:
    """Return admin dashboard metrics. Admin only."""
    conn = _get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

        unique_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM scans WHERE user_id IS NOT NULL"
        ).fetchone()[0]

        scans_by_day = [
            {"date": r[0], "count": r[1]}
            for r in conn.execute(
                """
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM scans
                GROUP BY day ORDER BY day DESC LIMIT 30
                """
            ).fetchall()
        ]

        most_scanned = [
            {"repo_url": r[0], "count": r[1]}
            for r in conn.execute(
                """
                SELECT repo_url, COUNT(*) as cnt
                FROM scans GROUP BY repo_url
                ORDER BY cnt DESC LIMIT 10
                """
            ).fetchall()
        ]

        avg_row = conn.execute("SELECT AVG(score) FROM scans WHERE score IS NOT NULL").fetchone()
        avg_score = round(avg_row[0], 1) if avg_row[0] else 0.0

        error_count = conn.execute("SELECT COUNT(*) FROM scans WHERE status = 'error'").fetchone()[
            0
        ]
        error_rate = round((error_count / total * 100), 1) if total > 0 else 0.0

        recent = [
            dict(r)
            for r in conn.execute(
                """
                SELECT s.scan_id, s.repo_url, s.status, s.score, s.created_at,
                       u.username
                FROM scans s
                LEFT JOIN users u ON s.user_id = u.id
                ORDER BY s.created_at DESC LIMIT 20
                """
            ).fetchall()
        ]
    finally:
        conn.close()

    return AdminMetrics(
        total_scans=total,
        unique_users=unique_users,
        scans_by_day=scans_by_day,
        most_scanned_repos=most_scanned,
        average_score=avg_score,
        error_rate=error_rate,
        recent_scans=recent,
    )


@app.get("/api/scan/{scan_id}/fix-report")
async def get_fix_report(scan_id: str) -> dict[str, Any]:
    """Generate a downloadable fix report with gap analysis and instructions."""
    import json
    import re

    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = dict(row)
    if row_dict["status"] != "complete":
        raise HTTPException(status_code=400, detail="Scan not complete")

    content = row_dict.get("content", "") or ""
    score = row_dict.get("score", 0) or 0
    repo_url = row_dict["repo_url"]
    files_scanned = row_dict.get("files_scanned", 0) or 0

    languages_raw = row_dict.get("languages", "{}")
    try:
        languages = json.loads(languages_raw) if languages_raw else {}
    except (json.JSONDecodeError, TypeError):
        languages = {}

    # --- Score breakdown ---
    expected_headings = [
        "Project Overview",
        "Current State",
        "Architecture",
        "Tech Stack",
        "Coding Standards",
        "Common Commands",
        "Anti-Patterns",
        "Dependencies",
        "Git Conventions",
    ]
    present_headings = [h for h in expected_headings if f"## {h}" in content]
    missing_headings = [h for h in expected_headings if f"## {h}" not in content]

    lines = content.splitlines()
    line_count = len(lines)
    code_block_count = content.count("```") // 2  # pairs
    bold_bullets = len(re.findall(r"- \*\*\w+", content))

    # Calculate sub-scores
    section_score = int((len(present_headings) / len(expected_headings)) * 60)
    depth_score = (10 if line_count > 50 else 0) + (5 if line_count > 100 else 0) + (5 if line_count > 150 else 0)
    code_score = 10 if code_block_count >= 2 else (5 if code_block_count >= 1 else 0)
    spec_score = 10 if bold_bullets > 5 else (5 if bold_bullets > 2 else 0)

    # --- Build fix actions sorted by point impact ---
    actions: list[dict[str, Any]] = []

    for heading in missing_headings:
        pts = round(60 / len(expected_headings))
        actions.append({
            "priority": "high" if pts >= 6 else "medium",
            "action": f"Add `## {heading}` section",
            "points": pts,
            "category": "sections",
        })

    if line_count <= 50:
        actions.append({
            "priority": "high",
            "action": "Expand content to 150+ lines for full depth score (+20 pts)",
            "points": 20,
            "category": "depth",
        })
    elif line_count <= 100:
        actions.append({
            "priority": "medium",
            "action": "Expand content to 150+ lines (+10 pts remaining)",
            "points": 10,
            "category": "depth",
        })
    elif line_count <= 150:
        actions.append({
            "priority": "low",
            "action": "Expand content past 150 lines (+5 pts remaining)",
            "points": 5,
            "category": "depth",
        })

    if code_block_count < 2:
        pts = 10 - code_score
        actions.append({
            "priority": "medium",
            "action": f"Add code blocks (need {2 - code_block_count} more) for full code score",
            "points": pts,
            "category": "code_blocks",
        })

    if bold_bullets <= 5:
        pts = 10 - spec_score
        actions.append({
            "priority": "medium",
            "action": f"Add bold-label bullets (`- **Key**: value`) — need {6 - bold_bullets} more",
            "points": pts,
            "category": "specificity",
        })

    actions.sort(key=lambda a: a["points"], reverse=True)

    # --- Section templates for missing headings ---
    section_templates = {
        "Project Overview": (
            "## Project Overview\n\n"
            "One-paragraph description of what this project does, who it's for, and its current maturity.\n\n"
            "- **Purpose**: [What problem does it solve?]\n"
            "- **Users**: [Who uses it?]\n"
            "- **Status**: [Alpha/Beta/Production]\n"
        ),
        "Current State": (
            "## Current State\n\n"
            "- **Version**: [x.y.z]\n"
            "- **Language**: [Primary language]\n"
            "- **Tests**: [count]\n"
            "- **Coverage**: [percentage]\n"
            "- **CI**: [passing/failing]\n"
        ),
        "Architecture": (
            "## Architecture\n\n"
            "```\nproject/\n"
            "├── src/          # Source code\n"
            "├── tests/        # Test suite\n"
            "├── docs/         # Documentation\n"
            "└── config/       # Configuration\n```\n\n"
            "Describe key modules, their responsibilities, and how data flows between them.\n"
        ),
        "Tech Stack": (
            "## Tech Stack\n\n"
            "- **Language**: [e.g., Python 3.12]\n"
            "- **Framework**: [e.g., FastAPI, React]\n"
            "- **Database**: [e.g., PostgreSQL, SQLite]\n"
            "- **Testing**: [e.g., pytest, Jest]\n"
            "- **CI/CD**: [e.g., GitHub Actions]\n"
        ),
        "Coding Standards": (
            "## Coding Standards\n\n"
            "- **Style**: [e.g., PEP 8, Airbnb JS]\n"
            "- **Naming**: [e.g., snake_case for Python]\n"
            "- **Type Hints**: [present/required]\n"
            "- **Line Length**: [e.g., 100 chars]\n"
            "- **Imports**: [absolute/relative, ordering]\n"
        ),
        "Common Commands": (
            "## Common Commands\n\n"
            "```bash\n"
            "# Install dependencies\n[your install command]\n\n"
            "# Run tests\n[your test command]\n\n"
            "# Lint / format\n[your lint command]\n\n"
            "# Build\n[your build command]\n```\n"
        ),
        "Anti-Patterns": (
            "## Anti-Patterns\n\n"
            "- Do NOT [common mistake in this codebase]\n"
            "- Do NOT [security anti-pattern]\n"
            "- Do NOT [style violation]\n"
        ),
        "Dependencies": (
            "## Dependencies\n\n"
            "### Runtime\n- [package]: [purpose]\n\n"
            "### Dev\n- [package]: [purpose]\n"
        ),
        "Git Conventions": (
            "## Git Conventions\n\n"
            "- **Commit style**: [e.g., Conventional commits: feat:, fix:, docs:]\n"
            "- **Branch naming**: [e.g., feat/description, fix/description]\n"
            "- **Review**: [e.g., PR required, 1 approval]\n"
        ),
    }

    # --- Build the markdown report ---
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    points_to_100 = 100 - score

    md = f"# Fix Report: {repo_name}\n\n"
    md += f"**Current Score**: {score}/100\n"
    md += f"**Points to 100**: {points_to_100}\n"
    md += f"**Files Scanned**: {files_scanned}\n"
    if languages:
        top_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
        md += f"**Languages**: {', '.join(f'{k} ({v})' for k, v in top_langs)}\n"
    md += f"\n---\n\n"

    # Score breakdown
    md += "## Score Breakdown\n\n"
    md += "| Category | Score | Max | Status |\n"
    md += "|----------|-------|-----|--------|\n"
    md += f"| Section Coverage | {section_score} | 60 | {len(present_headings)}/{len(expected_headings)} sections |\n"
    md += f"| Content Depth | {depth_score} | 20 | {line_count} lines |\n"
    md += f"| Code Blocks | {code_score} | 10 | {code_block_count} blocks |\n"
    md += f"| Specificity | {spec_score} | 10 | {bold_bullets} bold bullets |\n"
    md += f"| **Total** | **{score}** | **100** | |\n\n"

    # Priority actions
    if actions:
        md += "## Priority Actions\n\n"
        md += "Ordered by point impact (highest first):\n\n"
        for i, action in enumerate(actions, 1):
            badge = {"high": "HIGH", "medium": "MED", "low": "LOW"}[action["priority"]]
            md += f"{i}. **[{badge}]** {action['action']} (+{action['points']} pts)\n"
        md += "\n"

    # Missing section templates
    if missing_headings:
        md += "## Missing Sections — Copy-Paste Templates\n\n"
        md += "Add these sections to your CLAUDE.md to reach 100%. Fill in the bracketed placeholders.\n\n"
        for heading in missing_headings:
            template = section_templates.get(heading, f"## {heading}\n\n[Add content here]\n")
            md += f"### Template: {heading}\n\n"
            md += f"```markdown\n{template}```\n\n"

    # Claude Code prompt
    md += "## Quick Fix — Claude Code Prompt\n\n"
    md += "Paste this into Claude Code to auto-generate the missing content:\n\n"
    md += "```\n"
    if missing_headings:
        md += f"Read my CLAUDE.md and add the following missing sections: {', '.join(missing_headings)}. "
    if line_count <= 150:
        md += "Expand each section with specific details from the actual codebase. "
    if code_block_count < 2:
        md += "Include code blocks with real commands and examples. "
    if bold_bullets <= 5:
        md += "Use bold-label bullet points (- **Key**: value) for specificity. "
    md += "Target 150+ lines total. Keep it accurate to the actual project.\n"
    md += "```\n\n"

    # Existing sections (what's already good)
    if present_headings:
        md += "## Existing Sections (No Action Needed)\n\n"
        for h in present_headings:
            md += f"- {h}\n"
        md += "\n"

    md += "---\n\n"
    md += f"*Generated by [anchormd](https://anchormd.dev) on {datetime.now(UTC).strftime('%Y-%m-%d')}*\n"

    return {
        "scan_id": scan_id,
        "repo_url": repo_url,
        "score": score,
        "points_to_100": points_to_100,
        "actions": actions,
        "missing_sections": missing_headings,
        "present_sections": present_headings,
        "breakdown": {
            "sections": {"score": section_score, "max": 60, "present": len(present_headings), "total": len(expected_headings)},
            "depth": {"score": depth_score, "max": 20, "lines": line_count},
            "code_blocks": {"score": code_score, "max": 10, "count": code_block_count},
            "specificity": {"score": spec_score, "max": 10, "bold_bullets": bold_bullets},
        },
        "markdown": md,
    }


@app.get("/api/scan/{scan_id}/cursorrules")
async def get_cursorrules(scan_id: str) -> dict[str, Any]:
    """Convert a scan result to .cursorrules format for Cursor IDE."""
    import re

    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = dict(row)
    if row_dict["status"] != "complete" or not row_dict.get("content"):
        raise HTTPException(status_code=400, detail="Scan not complete")

    content = row_dict["content"]

    # Transform CLAUDE.md → .cursorrules format.
    # 1. Strip the "# CLAUDE.md — project" header, replace with cursorrules-style.
    content = re.sub(r"^# CLAUDE\.md — .+\n*", "", content)

    # 2. Rename section headings to Cursor conventions.
    renames = {
        "## Project Overview": "## Project Context",
        "## Anti-Patterns": "## Avoid",
        "## Common Commands": "## Commands",
        "## Git Conventions": "## Git",
    }
    for old, new in renames.items():
        content = content.replace(old, new)

    # 3. Add cursorrules preamble.
    repo_url = row_dict["repo_url"]
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    cursorrules = (
        f"# Cursor Rules — {repo_name}\n\n"
        "You are an expert developer working on this project. "
        "Follow these rules strictly.\n\n"
        + content.strip()
        + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": cursorrules,
        "filename": ".cursorrules",
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "service": "anchormd-web"}


# --- Static file serving (React frontend) ---

# Mount static files only if the dist directory exists (production).
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str) -> FileResponse:
        """Serve the React SPA. All non-API routes fall through to index.html."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
