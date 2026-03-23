"""FastAPI web application for anchormd — GitHub URL in, CLAUDE.md out."""

from __future__ import annotations

import asyncio
import hashlib
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
        # Migrate: add user_id and batch_id to scans if missing.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(scans)").fetchall()}
        if "user_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER")
        if "batch_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN batch_id TEXT")
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
                    "affiliation": "owner",
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
async def github_login(request: Request) -> dict[str, str]:
    """Return the GitHub OAuth authorize URL with redirect back to frontend."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    # Redirect back to frontend root so SPA handles the code exchange
    origin = str(request.base_url).rstrip("/")
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={origin}/"
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
            "html_url": r["html_url"],
        }
        for r in raw_repos
    ]


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
    )


# --- API Routes: Batch Scan ---


@app.post("/api/scan-all")
async def scan_all(
    request: ScanAllRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Queue scans for all repos belonging to the authenticated user."""
    token = user["access_token"]
    repos = await _fetch_all_repos(token)

    if not repos:
        raise HTTPException(status_code=404, detail="No repos found")

    batch_id = uuid.uuid4().hex[:12]
    now_ts = time.time()
    now_iso = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO scan_batches (id, user_id, repo_count, completed, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (batch_id, user["id"], len(repos), now_ts),
        )
        scan_ids = []
        for repo in repos:
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
            _scan_one(sid, repo["html_url"]) for sid, repo in zip(scan_ids, repos, strict=True)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    background_tasks.add_task(_run_batch)

    return {"batch_id": batch_id, "repo_count": len(repos)}


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
