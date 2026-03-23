"""FastAPI web application for anchormd — GitHub URL in, CLAUDE.md out."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.generator import generate_claude_md

logger = logging.getLogger(__name__)

# Database path — configurable via env but defaults to local.
DB_PATH = Path(__file__).parent / "scans.db"

# Static files path (built React frontend).
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"


def _get_db() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_db() -> None:
    """Create the scans table if it doesn't exist."""
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
                completed_at TEXT
            )
        """)
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
    version="0.1.0",
    lifespan=lifespan,
)


# --- Models ---


class ScanRequest(BaseModel):
    """Request body for POST /api/scan."""

    repo_url: str = Field(..., description="GitHub repository URL")


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


# --- Helpers ---


def _make_scan_id(repo_url: str) -> str:
    """Generate a deterministic scan ID from URL + timestamp."""
    raw = f"{repo_url}:{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _run_scan(scan_id: str, repo_url: str) -> None:
    """Execute the scan in a background thread."""
    import json

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
        conn.commit()
    except Exception:
        logger.exception("Failed to update scan %s", scan_id)
    finally:
        conn.close()


# --- API Routes ---


@app.post("/api/scan", response_model=ScanResponse)
async def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
) -> ScanResponse:
    """Accept a GitHub repo URL and start generating a CLAUDE.md."""
    scan_id = _make_scan_id(request.repo_url)
    now = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO scans (scan_id, repo_url, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (scan_id, request.repo_url, now),
        )
        conn.commit()
    finally:
        conn.close()

    background_tasks.add_task(_run_scan, scan_id, request.repo_url)

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
