"""FastAPI web application for anchormd — GitHub URL in, CLAUDE.md out."""

from __future__ import annotations

import asyncio
import hashlib
import json as json_module
import logging
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import stripe
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from web.generator import generate_claude_md

logger = logging.getLogger(__name__)

# --- Configuration ---

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
ADMIN_GITHUB_USERNAME = os.environ.get("ADMIN_GITHUB_USERNAME", "").strip()

# Fernet key(s) for encrypting GitHub access tokens at rest. Set via
# `fly secrets set ANCHORMD_TOKEN_KEY=$(
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# )`
# During rotation, supply comma-separated keys: new key first, old key second. The
# first key is used for encryption; every key is tried for decryption. Once all
# ciphertext has been re-encrypted by the new primary, drop the old key.
# Required — the app refuses to start without it.
_TOKEN_KEYS = [k.strip() for k in os.environ.get("ANCHORMD_TOKEN_KEY", "").split(",") if k.strip()]
_fernet: MultiFernet | None = (
    MultiFernet([Fernet(k.encode()) for k in _TOKEN_KEYS]) if _TOKEN_KEYS else None
)


def _encrypt_token(plain: str) -> bytes:
    """Encrypt a GitHub access token for storage with the primary key."""
    if _fernet is None:
        raise RuntimeError("ANCHORMD_TOKEN_KEY is not configured")
    return _fernet.encrypt(plain.encode())


def _decrypt_token(cipher: bytes | None) -> str | None:
    """Decrypt a stored GitHub access token, trying every configured key."""
    if _fernet is None or not cipher:
        return None
    try:
        return _fernet.decrypt(cipher).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt stored token — key rotated out or corrupt value")
        return None


def _hash_session_token(token: str) -> str:
    """Hash a session bearer token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# Sessions expire 30 days after last use; sliding window extended when within
# this threshold so active users aren't logged out mid-session.
_SESSION_TTL = timedelta(days=30)
_SESSION_RENEW_WHEN_UNDER = timedelta(days=7)


def _gh_token_for(user: dict[str, Any]) -> str:
    """Return the decrypted GitHub access token for a user, or raise 401."""
    plain = _decrypt_token(user.get("access_token_encrypted"))
    if not plain:
        raise HTTPException(
            status_code=401,
            detail="GitHub credentials unavailable — please sign in again",
        )
    return plain


# Stripe configuration.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
DEEP_SCAN_PRICE_CENTS = 1900  # $19.00 one-time
SITE_URL = os.environ.get("SITE_URL", "https://anchormd.dev")
LICENSE_SERVER_URL = os.environ.get("ANCHORMD_LICENSE_SERVER", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OAUTH_REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "https://anchormd.dev/")
SESSION_TOKEN_BYTES = 32
OAUTH_STATE_TTL_SECONDS = 600

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Database path — configurable via env but defaults to local.
DB_PATH = Path(os.environ.get("ANCHORMD_DB_PATH", Path(__file__).parent / "scans.db"))

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
                batch_id TEXT,
                repo_private INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                github_id INTEGER UNIQUE,
                username TEXT,
                avatar_url TEXT,
                access_token TEXT,
                session_token_hash TEXT,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                created_at REAL NOT NULL
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                expires_at TEXT,
                revoked INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        # Migrate: add expires_at if missing.
        session_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "expires_at" not in session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
        # Migrate: add columns to scans if missing.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(scans)").fetchall()}
        if "user_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER")
        if "batch_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN batch_id TEXT")
        if "repo_private" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN repo_private INTEGER DEFAULT 0")
        if "scan_type" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN scan_type TEXT DEFAULT 'free'")
        if "recommendations" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN recommendations TEXT")
        if "stripe_session_id" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN stripe_session_id TEXT")
        if "email" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN email TEXT")
        if "category_scores" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN category_scores TEXT")
        # Migrate: add last_seen_at + access_token_encrypted to users if missing.
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "last_seen_at" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN last_seen_at TEXT")
        if "access_token_encrypted" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN access_token_encrypted BLOB")
        # One-shot: scrub legacy plaintext GitHub tokens so they're not recoverable
        # from the SQLite file. Users will need to re-authenticate (their bearer
        # token in localStorage is also invalid after this point).
        conn.execute("UPDATE users SET access_token = NULL WHERE access_token IS NOT NULL")
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # noqa: ANN401
    """Initialize database on startup."""
    if not ADMIN_GITHUB_USERNAME:
        raise RuntimeError(
            "ADMIN_GITHUB_USERNAME is not set. Refusing to start — "
            "every user would be locked out of admin endpoints, or worse, "
            "a stale default could silently grant admin to an unintended account."
        )
    if _fernet is None:
        raise RuntimeError(
            "ANCHORMD_TOKEN_KEY is not set. Refusing to start — "
            "GitHub access tokens would be stored in plaintext."
        )
    _init_db()
    yield


def _rate_limit_key(request: Request) -> str:
    """Prefer trusted forwarded IP (Fly sets Fly-Client-IP), fall back to peer."""
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=["120/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply hardening headers to every response."""

    _HEADERS = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), "
            'payment=(self "https://checkout.stripe.com"), usb=()'
        ),
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://avatars.githubusercontent.com "
            "https://*.githubusercontent.com; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self' https://checkout.stripe.com https://github.com; "
            "object-src 'none'"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
    }

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        for k, v in self._HEADERS.items():
            response.headers.setdefault(k, v)
        return response


app = FastAPI(
    title="anchormd",
    description="Generate CLAUDE.md files from GitHub repos",
    version="0.2.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)


# --- Models ---


# GitHub: owner = 1-39 chars, alphanumeric or hyphens (no leading/trailing hyphen,
# no consecutive hyphens). Repo = 1-100 chars, alphanumeric plus . _ -
# Accepts a trailing `.git`, `/tree/...`, `/blob/...` etc. but only extracts owner/repo.
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38})/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?(?:/.*)?$"
)
_GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

# Paths that live under github.com but aren't user repos.
_GITHUB_RESERVED_OWNERS = frozenset(
    {
        "orgs",
        "search",
        "settings",
        "marketplace",
        "notifications",
        "pulls",
        "issues",
        "stars",
        "explore",
        "topics",
        "trending",
        "login",
        "logout",
        "sessions",
        "sponsors",
        "about",
        "features",
        "enterprise",
        "pricing",
        "security",
        "contact",
        "api",
    }
)


def _validate_github_url(value: str) -> str:
    """Allow only https://github.com/<owner>/<repo>, normalizing extra path.

    Blocks SSRF attempts (private IPs, internal hostnames, non-HTTP schemes) and
    non-repo GitHub paths (/orgs/..., /search?q=..., raw content, etc.).
    """
    if not isinstance(value, str):
        raise ValueError("repo_url must be a string")
    stripped = value.strip()
    if any(c.isspace() or ord(c) < 0x20 for c in stripped):
        raise ValueError("repo_url contains invalid characters")
    match = _GITHUB_URL_RE.match(stripped)
    if not match:
        raise ValueError("repo_url must be https://github.com/<owner>/<repo>")
    owner = match.group("owner")
    repo = match.group("repo").removesuffix(".git")
    if owner.lower() in _GITHUB_RESERVED_OWNERS:
        raise ValueError("repo_url must point to a user or organization repository")
    return f"https://github.com/{owner}/{repo}"


class ScanRequest(BaseModel):
    """Request body for POST /api/scan."""

    repo_url: str = Field(..., description="GitHub repository URL")

    @field_validator("repo_url")
    @classmethod
    def _check_repo_url(cls, v: str) -> str:
        return _validate_github_url(v)


class ScanAllRequest(BaseModel):
    """Request body for POST /api/scan-all."""

    username: str = Field(..., description="GitHub username")


class ScanResponse(BaseModel):
    """Response for a scan result."""

    scan_id: str
    repo_url: str
    content: str | None = None
    score: int | None = None
    category_scores: dict[str, Any] | None = None
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

    @field_validator("repo_url")
    @classmethod
    def _check_repo_url(cls, v: str) -> str:
        return _validate_github_url(v)


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
    llm_analysis: dict[str, Any] | None = None
    dependency_audit: dict[str, Any] | None = None
    category_scores: dict[str, Any] | None = None
    tech_debt: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None
    hygiene: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    scan_type: str = "deep"
    status: str = "pending"
    created_at: str | None = None
    completed_at: str | None = None


class AdminMetrics(BaseModel):
    """Admin dashboard metrics."""

    total_scans: int
    unique_users: int
    total_users: int
    dau: int
    wau: int
    scans_by_day: list[dict[str, Any]]
    new_users_by_day: list[dict[str, Any]]
    most_scanned_repos: list[dict[str, Any]]
    average_score: float
    error_rate: float
    recent_scans: list[dict[str, Any]]


def _hash_session_token(token: str) -> str:
    """Store session tokens as hashes so the database doesn't hold bearer secrets."""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_session_token() -> str:
    """Generate a new opaque app session token."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def _extract_repo_coordinates(repo_url: str) -> tuple[str, str]:
    """Parse owner/repo from a GitHub URL or git URL."""
    parts = [p for p in urlparse(repo_url).path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError("Cannot parse repo from URL")
    return parts[0], parts[1].replace(".git", "")


async def _fetch_repo_metadata(repo_url: str, token: str | None = None) -> dict[str, Any]:
    """Fetch repo visibility and canonical URL from GitHub."""
    try:
        normalized = _validate_github_url(repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    owner, repo = _extract_repo_coordinates(normalized)
    if not _GITHUB_OWNER_RE.fullmatch(owner) or not _GITHUB_REPO_RE.fullmatch(repo):
        raise HTTPException(status_code=400, detail="Invalid repository path")
    github_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(github_api_url, headers=headers, follow_redirects=False)

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Repository not found")
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Repository is not accessible")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to inspect repository")

    payload = resp.json()
    return {
        "repo_url": payload["html_url"],
        "private": bool(payload.get("private", False)),
        "default_branch": payload.get("default_branch"),
    }


def _get_scan_row(scan_id: str) -> sqlite3.Row | None:
    """Load a scan row by ID."""
    conn = _get_db()
    try:
        return conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    finally:
        conn.close()


def _ensure_scan_access(row: sqlite3.Row, user: dict[str, Any] | None) -> dict[str, Any]:
    """Enforce access rules for public and private scan results."""
    row_dict = dict(row)
    if row_dict.get("repo_private") and row_dict.get("user_id") != (user or {}).get("id"):
        raise HTTPException(status_code=403, detail="This scan belongs to another user")
    return row_dict


# --- Auth Helpers ---


async def _get_current_user(request: Request) -> dict[str, Any] | None:
    """Extract user from Authorization header. Returns None if not authenticated."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    token_hash = _hash_session_token(token)
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    conn = _get_db()
    try:
        session = conn.execute(
            "SELECT user_id, revoked, expires_at FROM sessions WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if not session or session["revoked"]:
            return None
        expires_at_raw = session["expires_at"]
        new_expires_at: str | None = None
        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
            except ValueError:
                expires_at = None
            if expires_at is None:
                # Malformed — treat as expired, force re-auth.
                return None
            if now_dt >= expires_at:
                return None
            if expires_at - now_dt < _SESSION_RENEW_WHEN_UNDER:
                new_expires_at = (now_dt + _SESSION_TTL).isoformat()
        if new_expires_at:
            conn.execute(
                "UPDATE sessions SET last_used_at = ?, expires_at = ? WHERE token_hash = ?",
                (now, new_expires_at, token_hash),
            )
        else:
            conn.execute(
                "UPDATE sessions SET last_used_at = ? WHERE token_hash = ?",
                (now, token_hash),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
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
    if not ADMIN_GITHUB_USERNAME or user.get("username") != ADMIN_GITHUB_USERNAME:
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
            # Surface category breakdown on the free tier so the overall
            # number doesn't hide weak subcategories. Deep scan recomputes
            # with real CVE data — the free version passes an empty
            # vulnerability list, so Security/Deps reflect structural
            # signals only (which is the upsell hook).
            category_scores = _compute_category_scores(result.content or "", [])
            conn.execute(
                """
                UPDATE scans
                SET status = 'complete', content = ?, score = ?,
                    files_scanned = ?, languages = ?, completed_at = ?,
                    category_scores = ?
                WHERE scan_id = ?
                """,
                (
                    result.content,
                    result.score,
                    result.files_scanned,
                    json.dumps(result.languages),
                    now,
                    json.dumps(category_scores),
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
@limiter.limit("20/minute")
async def github_login(request: Request) -> dict[str, str]:
    """Return the GitHub OAuth authorize URL."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    state = secrets.token_urlsafe(24)
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO oauth_states (state, created_at) VALUES (?, ?)",
            (state, time.time()),
        )
        conn.execute(
            "DELETE FROM oauth_states WHERE created_at < ?",
            (time.time() - OAUTH_STATE_TTL_SECONDS,),
        )
        conn.commit()
    finally:
        conn.close()

    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&state={state}"
        f"&scope=repo,read:user"
    )
    return {"url": url}


@app.get("/api/auth/callback")
@limiter.limit("10/minute")
async def github_callback(request: Request, code: str, state: str) -> dict[str, Any]:
    """Exchange GitHub OAuth code for access token and upsert user."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    conn = _get_db()
    try:
        state_row = conn.execute(
            "SELECT state, created_at FROM oauth_states WHERE state = ?",
            (state,),
        ).fetchone()
        if not state_row:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
        if time.time() - state_row["created_at"] > OAUTH_STATE_TTL_SECONDS:
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            conn.commit()
            raise HTTPException(status_code=400, detail="Expired OAuth state")
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        conn.commit()
    finally:
        conn.close()

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

    # Upsert user with encrypted token. Plaintext column is always NULL going forward.
    encrypted_token = _encrypt_token(access_token)
    now_dt = datetime.now(UTC)
    now_iso = now_dt.isoformat()
    expires_iso = (now_dt + _SESSION_TTL).isoformat()
    session_token = secrets.token_urlsafe(32)
    session_hash = _hash_session_token(session_token)

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO users (github_id, username, avatar_url,
                               access_token, access_token_encrypted, created_at)
            VALUES (?, ?, ?, NULL, ?, ?)
            ON CONFLICT(github_id) DO UPDATE SET
                username = excluded.username,
                avatar_url = excluded.avatar_url,
                access_token = NULL,
                access_token_encrypted = excluded.access_token_encrypted
            """,
            (
                user_data["id"],
                user_data["login"],
                user_data.get("avatar_url", ""),
                encrypted_token,
                time.time(),
            ),
        )
        row = conn.execute(
            "SELECT id FROM users WHERE github_id = ?", (user_data["id"],)
        ).fetchone()
        user_id = dict(row)["id"] if row else None
        if user_id is None:
            raise HTTPException(status_code=500, detail="Failed to persist user")
        conn.execute(
            """
            INSERT INTO sessions (token_hash, user_id, created_at, last_used_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_hash, user_id, now_iso, now_iso, expires_iso),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "token": session_token,
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
    now = datetime.now(UTC).isoformat()
    conn = _get_db()
    try:
        conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return {
        "id": user["id"],
        "github_id": user["github_id"],
        "username": user["username"],
        "avatar_url": user["avatar_url"],
        "is_admin": user["username"] == ADMIN_GITHUB_USERNAME,
    }


@app.post("/api/auth/logout")
@limiter.limit("30/minute")
async def logout(request: Request) -> dict[str, str]:
    """Revoke the current session. Idempotent — returns ok even if no session."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_hash = _hash_session_token(auth_header[7:])
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE sessions SET revoked = 1 WHERE token_hash = ?",
                (token_hash,),
            )
            conn.commit()
        finally:
            conn.close()
    return {"status": "ok"}


@app.post("/api/auth/logout-all")
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Revoke every session for the current user."""
    conn = _get_db()
    try:
        cur = conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ? AND revoked = 0",
            (user["id"],),
        )
        conn.commit()
        revoked = cur.rowcount
    finally:
        conn.close()
    return {"status": "ok", "revoked_sessions": revoked}


# --- API Routes: Repos ---


@app.get("/api/repos")
async def list_repos(
    user: dict[str, Any] = Depends(_require_user),
) -> list[dict[str, Any]]:
    """List all repos for the authenticated user."""
    token = _gh_token_for(user)
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


def _get_cached_free_scan(repo_url: str, user_id: int | None, repo_private: bool) -> dict | None:
    """Return a cached free scan when it is safe to reuse."""
    conn = _get_db()
    try:
        if repo_private:
            if user_id is None:
                return None
            row = conn.execute(
                "SELECT scan_id, status FROM scans "
                "WHERE repo_url = ? AND scan_type = 'free' AND status = 'complete' "
                "AND repo_private = 1 AND user_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (repo_url, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT scan_id, status FROM scans "
                "WHERE repo_url = ? AND scan_type = 'free' AND status = 'complete' "
                "AND repo_private = 0 "
                "ORDER BY created_at DESC LIMIT 1",
                (repo_url,),
            ).fetchone()
        if row:
            return {"scan_id": row["scan_id"], "status": row["status"], "cached": True}
    finally:
        conn.close()
    return None


_DEDUP_WINDOW_SECONDS = 30


def _find_recent_inflight_scan(repo_url: str) -> dict | None:
    """Return a pending or recently-errored free scan for the same repo.

    Prevents the retry-storm pattern (observed in prod: 11 rows for one dead
    URL in 10s). Window is 30s — after that, a retry is considered intentional.
    """
    cutoff = (datetime.now(UTC) - timedelta(seconds=_DEDUP_WINDOW_SECONDS)).isoformat()
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT scan_id, status, error, created_at FROM scans "
            "WHERE repo_url = ? AND scan_type = 'free' "
            "AND status IN ('pending', 'error') "
            "AND created_at >= ? "
            "ORDER BY created_at DESC LIMIT 1",
            (repo_url, cutoff),
        ).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


# --- API Routes: Scan ---


@app.post("/api/scan", response_model=ScanResponse)
@limiter.limit("30/minute")
async def create_scan(
    request: Request,
    payload: ScanRequest,
    background_tasks: BackgroundTasks,
) -> ScanResponse:
    """Accept a GitHub repo URL and start generating a CLAUDE.md."""
    user = await _get_current_user(request)
    user_id = user["id"] if user else None
    token = _decrypt_token(user.get("access_token_encrypted")) if user else None
    repo = await _fetch_repo_metadata(payload.repo_url, token=token)
    canonical_repo_url = repo["repo_url"]
    repo_private = bool(repo["private"])

    # Return cached result for repeat free scans of the same repo
    cached = _get_cached_free_scan(canonical_repo_url, user_id, repo_private)
    if cached:
        return ScanResponse(
            scan_id=cached["scan_id"],
            repo_url=canonical_repo_url,
            status="complete",
            created_at="",
        )

    # Dedup retry storms: if a pending or recently-errored scan exists for
    # the same repo within the dedup window, return it instead of starting
    # a duplicate job. A client hitting the same URL repeatedly — whether
    # a user double-clicking or a script in a tight loop — gets the same
    # scan_id back and can poll that one.
    inflight = _find_recent_inflight_scan(canonical_repo_url)
    if inflight:
        return ScanResponse(
            scan_id=inflight["scan_id"],
            repo_url=canonical_repo_url,
            status=inflight["status"],
            error=inflight.get("error"),
            created_at=inflight["created_at"],
        )

    scan_id = _make_scan_id(canonical_repo_url)
    now = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO scans (scan_id, repo_url, status, created_at, user_id, repo_private)
            VALUES (?, ?, 'pending', ?, ?, ?)
            """,
            (scan_id, canonical_repo_url, now, user_id, int(repo_private)),
        )
        conn.commit()
    finally:
        conn.close()

    background_tasks.add_task(_run_scan, scan_id, canonical_repo_url, token)

    return ScanResponse(
        scan_id=scan_id,
        repo_url=canonical_repo_url,
        status="pending",
        created_at=now,
    )


@app.get("/api/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str, request: Request) -> ScanResponse:
    """Retrieve a previous scan result."""
    import json

    user = await _get_current_user(request)
    row = _get_scan_row(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = _ensure_scan_access(row, user)
    languages_raw = row_dict.get("languages", "{}")
    try:
        languages = json.loads(languages_raw) if languages_raw else {}
    except (json.JSONDecodeError, TypeError):
        languages = {}

    category_scores_raw = row_dict.get("category_scores")
    try:
        category_scores = json.loads(category_scores_raw) if category_scores_raw else None
    except (json.JSONDecodeError, TypeError):
        category_scores = None

    return ScanResponse(
        scan_id=row_dict["scan_id"],
        repo_url=row_dict["repo_url"],
        content=row_dict.get("content"),
        score=row_dict.get("score"),
        category_scores=category_scores,
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
@limiter.limit("2/minute")
async def scan_all(
    request: Request,
    payload: ScanAllRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Queue scans for all repos belonging to the authenticated user.

    Repos with a previous score of 100 that haven't been pushed to since the
    last scan are skipped and their cached result is reused.
    """

    token = _gh_token_for(user)
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
                    user_id, batch_id, repo_private)
                VALUES (?, ?, 'complete', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    url,
                    cached["score"],
                    cached["content"],
                    cached["files_scanned"],
                    cached["languages"],
                    now_iso,
                    now_iso,
                    user["id"],
                    batch_id,
                    int(repo["private"]),
                ),
            )

        # Insert pending scans for repos that need re-scanning.
        scan_ids = []
        for repo in to_scan:
            scan_id = _make_scan_id(repo["html_url"])
            scan_ids.append(scan_id)
            conn.execute(
                """
                INSERT INTO scans (
                    scan_id, repo_url, status, created_at, user_id, batch_id, repo_private
                )
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (scan_id, repo["html_url"], now_iso, user["id"], batch_id, int(repo["private"])),
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


def _build_file_tree(repo_path: Path, max_depth: int = 3, max_entries: int = 100) -> str:
    """Build a compact file tree string for LLM context."""
    lines: list[str] = []
    count = 0

    def _walk(path: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= max_entries:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") or entry.name == "node_modules":
                continue
            if count >= max_entries:
                lines.append(f"{prefix}...")
                return
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                count += 1
                _walk(entry, prefix + "  ", depth + 1)
            else:
                lines.append(f"{prefix}{entry.name}")
                count += 1

    _walk(repo_path, "", 0)
    return "\n".join(lines)


def _parse_dependencies(repo_path: Path) -> list[dict[str, str]]:
    """Parse dependency files and extract package names with versions."""
    deps: list[dict[str, str]] = []

    # requirements.txt
    req_file = repo_path / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
                if sep in line:
                    name, version = line.split(sep, 1)
                    deps.append(
                        {
                            "name": name.strip(),
                            "version": version.strip().split(",")[0],
                            "ecosystem": "PyPI",
                        }
                    )
                    break
            else:
                if line and not line.startswith("git+"):
                    deps.append({"name": line, "version": "", "ecosystem": "PyPI"})

    # pyproject.toml dependencies
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            import re as _re

            content = pyproject.read_text(errors="replace")
            # Simple extraction of dependencies array entries
            in_deps = False
            for line in content.splitlines():
                if _re.match(r"^dependencies\s*=\s*\[", line):
                    in_deps = True
                    continue
                if in_deps:
                    if "]" in line:
                        in_deps = False
                        continue
                    match = _re.search(r'"([^"]+)"', line)
                    if match:
                        dep_str = match.group(1)
                        for sep in ("==", ">=", "<=", "~=", "!="):
                            if sep in dep_str:
                                name, ver = dep_str.split(sep, 1)
                                deps.append(
                                    {
                                        "name": name.strip(),
                                        "version": ver.strip().split(",")[0],
                                        "ecosystem": "PyPI",
                                    }
                                )
                                break
                        else:
                            deps.append(
                                {
                                    "name": dep_str.split(">")[0].split("<")[0].strip(),
                                    "version": "",
                                    "ecosystem": "PyPI",
                                }
                            )
        except Exception:
            pass

    # package.json
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            pkg = json_module.loads(pkg_json.read_text(errors="replace"))
            for section in ("dependencies", "devDependencies"):
                for name, ver in pkg.get(section, {}).items():
                    clean_ver = ver.lstrip("^~>=<")
                    deps.append({"name": name, "version": clean_ver, "ecosystem": "npm"})
        except Exception:
            pass

    # Cargo.toml
    cargo = repo_path / "Cargo.toml"
    if cargo.exists():
        try:
            import re as _re

            content = cargo.read_text(errors="replace")
            in_deps = False
            for line in content.splitlines():
                if _re.match(r"^\[dependencies\]", line):
                    in_deps = True
                    continue
                if in_deps and line.startswith("["):
                    break
                if in_deps and "=" in line:
                    parts = line.split("=", 1)
                    name = parts[0].strip()
                    ver_str = parts[1].strip().strip('"').strip("'")
                    if ver_str.startswith("{"):
                        match = _re.search(r'version\s*=\s*"([^"]+)"', ver_str)
                        ver_str = match.group(1) if match else ""
                    deps.append({"name": name, "version": ver_str, "ecosystem": "crates.io"})
        except Exception:
            pass

    # Deduplicate by (name, ecosystem)
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for d in deps:
        key = (d["name"].lower(), d["ecosystem"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _check_vulnerabilities(deps: list[dict[str, str]]) -> dict[str, Any]:
    """Check dependencies against OSV.dev for known vulnerabilities."""
    if not deps:
        return {"total_packages": 0, "vulnerabilities": [], "ecosystem": "unknown"}

    # Only query deps with pinned versions
    queryable = [d for d in deps if d.get("version")]
    if not queryable:
        return {
            "total_packages": len(deps),
            "vulnerabilities": [],
            "ecosystem": deps[0]["ecosystem"] if deps else "unknown",
        }

    queries = [
        {"package": {"name": d["name"], "ecosystem": d["ecosystem"]}, "version": d["version"]}
        for d in queryable
    ]

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post("https://api.osv.dev/v1/querybatch", json={"queries": queries})
            resp.raise_for_status()
            results = resp.json().get("results", [])
    except Exception as exc:
        logger.warning("OSV.dev query failed: %s", exc)
        return {"total_packages": len(deps), "vulnerabilities": [], "error": str(exc)}

    vulns: list[dict[str, Any]] = []
    for i, result in enumerate(results):
        for vuln in result.get("vulns", []):
            severity = "unknown"
            for s in vuln.get("severity", []):
                if s.get("type") == "CVSS_V3":
                    score_str = s.get("score", "")
                    try:
                        cvss = float(score_str) if score_str else 0
                    except (ValueError, TypeError):
                        cvss = 0
                    if cvss >= 9.0:
                        severity = "critical"
                    elif cvss >= 7.0:
                        severity = "high"
                    elif cvss >= 4.0:
                        severity = "medium"
                    else:
                        severity = "low"

            fix_version = None
            for affected in vuln.get("affected", []):
                for r in affected.get("ranges", []):
                    for ev in r.get("events", []):
                        if "fixed" in ev:
                            fix_version = ev["fixed"]

            vulns.append(
                {
                    "package": queryable[i]["name"],
                    "version": queryable[i]["version"],
                    "cve_id": vuln.get("aliases", [vuln.get("id", "")])[0]
                    if vuln.get("aliases")
                    else vuln.get("id", ""),
                    "severity": severity,
                    "summary": vuln.get("summary", "No description available")[:200],
                    "fix_version": fix_version,
                }
            )

    return {
        "total_packages": len(deps),
        "vulnerabilities": vulns,
        "ecosystem": deps[0]["ecosystem"] if deps else "unknown",
    }


def _run_llm_analysis(
    claude_md: str,
    file_tree: str,
    dep_audit: dict[str, Any],
    tech_debt_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send CLAUDE.md + context to Claude for architecture/security analysis."""
    if not ANTHROPIC_API_KEY:
        return {"error": "AI analysis not configured"}

    vuln_summary = ""
    for v in dep_audit.get("vulnerabilities", []):
        vuln_summary += f"- {v['package']} {v['version']}: {v['cve_id']} ({v['severity']})\n"

    debt_summary = ""
    if tech_debt_signals:
        for s in tech_debt_signals[:20]:
            debt_summary += (
                f"- [{s['severity']}] {s['file']}:{s.get('line', '?')} — {s['message']}\n"
            )

    vuln_section = (
        f"## Known Vulnerabilities{chr(10)}{vuln_summary}"
        if vuln_summary
        else "No known vulnerabilities found."
    )
    debt_section = (
        f"## Tech Debt Signals{chr(10)}{debt_summary}"
        if debt_summary
        else "No significant tech debt signals."
    )

    prompt = f"""Analyze this repository. You are a senior engineer doing a paid code review.
Be specific, reference actual files, and include code examples for every recommendation.

## File Tree
```
{file_tree[:3000]}
```

## Generated CLAUDE.md
```markdown
{claude_md[:6000]}
```

{vuln_section}

{debt_section}

Respond in this exact JSON format:
{{
  "architecture": "2-3 paragraph assessment of the project architecture, organization,
                   and patterns. Reference specific directories and files.
                   Identify strengths and weaknesses.",
  "security": "2-3 paragraph security review. Cover credential handling,
               input validation, dependency risks, and specific concerns from
               the file tree and code structure.",
  "improvements": [
    {{
      "priority": "high|medium|low",
      "title": "Short title",
      "description": "Specific, actionable recommendation explaining WHY this matters",
      "file": "path/to/relevant/file (if applicable, else null)",
      "code_before": "problematic code snippet or null if new addition",
      "code_after": "improved code snippet showing the fix"
    }},
    ... (provide 5-8 items, most impactful first, each with concrete code examples)
  ]
}}

Rules:
- Every improvement MUST include code_before/code_after showing the actual fix
  (use null for code_before only when recommending adding a new file)
- Reference real files from the tree, not hypothetical ones
- No generic advice like "add tests" — specify WHICH code needs testing and show
  a test skeleton
- Be direct and opinionated"""

    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]

            import re as _re

            json_match = _re.search(r"\{[\s\S]*\}", text)
            if json_match:
                return json_module.loads(json_match.group())
            return {"error": "Could not parse LLM response"}
    except Exception as exc:
        logger.warning("LLM analysis failed: %s", exc)
        return {"error": f"AI analysis unavailable: {type(exc).__name__}"}


def _check_compliance(repo_path: Path) -> dict[str, Any]:
    """Check for standard repo files and best practices."""
    checks = {
        "LICENSE": {"path": "LICENSE*", "label": "License file", "weight": "high"},
        "README": {"path": "README*", "label": "README", "weight": "high"},
        "CHANGELOG": {"path": "CHANGELOG*", "label": "Changelog", "weight": "medium"},
        "CONTRIBUTING": {"path": "CONTRIBUTING*", "label": "Contributing guide", "weight": "low"},
        "SECURITY": {"path": "SECURITY*", "label": "Security policy", "weight": "medium"},
        "gitignore": {"path": ".gitignore", "label": ".gitignore", "weight": "high"},
        "CI config": {"path": ".github/workflows/*", "label": "CI/CD workflows", "weight": "high"},
        "Lock file": {"path": None, "label": "Dependency lock file", "weight": "medium"},
        "Type config": {"path": None, "label": "Type checking config", "weight": "low"},
        "Editor config": {"path": ".editorconfig", "label": "Editor config", "weight": "low"},
    }

    results: list[dict[str, Any]] = []
    import glob as _glob

    for name, check in checks.items():
        if name == "Lock file":
            found = any(
                (repo_path / f).exists()
                for f in (
                    "package-lock.json",
                    "yarn.lock",
                    "pnpm-lock.yaml",
                    "Pipfile.lock",
                    "poetry.lock",
                    "Cargo.lock",
                    "uv.lock",
                )
            )
        elif name == "Type config":
            found = any(
                (repo_path / f).exists()
                for f in (
                    "tsconfig.json",
                    "mypy.ini",
                    "pyrightconfig.json",
                    "pyproject.toml",
                )  # pyproject often has [tool.mypy]
            )
        elif check["path"]:
            found = bool(_glob.glob(str(repo_path / check["path"])))
        else:
            found = False

        results.append(
            {
                "name": name,
                "label": check["label"],
                "found": found,
                "weight": check["weight"],
            }
        )

    passed = sum(1 for r in results if r["found"])
    total = len(results)
    score = round((passed / total) * 100) if total else 0

    return {"checks": results, "passed": passed, "total": total, "score": score}


def _run_context_hygiene(claude_md: str) -> dict[str, Any]:
    """Run context-hygiene analysis on the generated CLAUDE.md."""
    try:
        from context_hygiene.contradictions import contradictions_fast
        from context_hygiene.deadweight import deadweight_fast
        from context_hygiene.models import Segment
        from context_hygiene.staleness import staleness_fast

        # Treat each major section as a segment
        sections = claude_md.split("\n## ")
        segments = []
        for i, section in enumerate(sections):
            text = section if i == 0 else f"## {section}"
            segments.append(
                Segment(
                    index=i,
                    role="assistant",
                    content=text,
                    token_estimate=len(text.split()),
                )
            )

        if not segments:
            return {"error": "No content to analyze"}

        stale = staleness_fast(segments)
        dead = deadweight_fast(segments)
        contradictions = contradictions_fast(segments)

        stale_issues = [
            {"section": s.segment_index, "score": round(s.score, 2), "reasons": s.reasons}
            for s in stale
            if s.score > 0.3
        ]
        dead_issues = [
            {
                "section": d.segment_index,
                "reason": d.reason,
                "tokens_recoverable": d.tokens_recoverable,
            }
            for d in dead
        ]
        contradiction_issues = [
            {"description": c.description, "confidence": round(c.confidence, 2)}
            for c in contradictions
            if c.confidence > 0.5
        ]

        total_issues = len(stale_issues) + len(dead_issues) + len(contradiction_issues)
        if total_issues == 0:
            grade = "A"
        elif total_issues <= 2:
            grade = "B"
        elif total_issues <= 5:
            grade = "C"
        else:
            grade = "D"

        return {
            "grade": grade,
            "staleness": stale_issues,
            "deadweight": dead_issues,
            "contradictions": contradiction_issues,
            "total_issues": total_issues,
        }
    except ImportError:
        return {"error": "context-hygiene not available"}
    except Exception as exc:
        logger.warning("Context hygiene analysis failed: %s", exc)
        return {"error": f"Analysis failed: {type(exc).__name__}"}


def _get_scan_history(repo_url: str, current_scan_id: str) -> dict[str, Any] | None:
    """Get previous deep scan results for the same repo to show improvement."""
    conn = _get_db()
    try:
        row = conn.execute(
            """
            SELECT scan_id, score, completed_at, recommendations
            FROM scans
            WHERE repo_url = ? AND scan_type = 'deep' AND status = 'complete'
                  AND scan_id != ?
            ORDER BY completed_at DESC LIMIT 1
            """,
            (repo_url, current_scan_id),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    prev = dict(row)
    prev_recs = {}
    with suppress(json_module.JSONDecodeError, TypeError):
        prev_recs = json_module.loads(prev.get("recommendations", "{}"))

    prev_scores = prev_recs.get("category_scores", {}) if isinstance(prev_recs, dict) else {}
    return {
        "previous_scan_id": prev["scan_id"],
        "previous_score": prev.get("score"),
        "previous_date": prev.get("completed_at"),
        "previous_categories": prev_scores.get("categories", {}),
    }


def _compute_category_scores(content: str, vulnerabilities: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute category scores with letter grades for the deep scan report."""

    def _grade(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    content_lower = content.lower()

    # Structure (25%)
    structure_score = 40  # base
    if "## Architecture" in content or "## Project" in content:
        structure_score += 20
    if "```" in content and ("├" in content or "└" in content or "directory" in content_lower):
        structure_score += 15
    if "## Coding Standards" in content or "## Code Style" in content:
        structure_score += 15
    if "## Anti-Patterns" in content:
        structure_score += 10
    structure_score = min(structure_score, 100)

    # Security (25%)
    security_score = 50  # base
    if "## Security" in content or "security" in content_lower:
        security_score += 15
    if "credential" in content_lower or "secret" in content_lower or "api key" in content_lower:
        security_score += 10
    if "validation" in content_lower or "sanitiz" in content_lower:
        security_score += 10
    if "## Environment" in content or "env" in content_lower:
        security_score += 10
    # Penalty for vulnerabilities
    crit_count = sum(1 for v in vulnerabilities if v.get("severity") in ("critical", "high"))
    med_count = sum(1 for v in vulnerabilities if v.get("severity") == "medium")
    security_score -= crit_count * 15 + med_count * 5
    security_score = max(0, min(security_score, 100))

    # CI/CD (15%)
    ci_score = 30  # base
    if "## CI" in content or "ci/cd" in content_lower or "workflow" in content_lower:
        ci_score += 25
    if "github actions" in content_lower or ".github/workflows" in content_lower:
        ci_score += 20
    if "deploy" in content_lower:
        ci_score += 15
    if "lint" in content_lower or "format" in content_lower:
        ci_score += 10
    ci_score = min(ci_score, 100)

    # Dependencies (20%)
    deps_score = 50  # base
    if "## Dependencies" in content or "## Tech Stack" in content:
        deps_score += 20
    if (
        "requirements" in content_lower
        or "package.json" in content_lower
        or "pyproject" in content_lower
    ):
        deps_score += 15
    # Penalty for vulnerabilities
    deps_score -= crit_count * 20 + med_count * 8
    if not vulnerabilities:
        deps_score += 15  # bonus for clean deps
    deps_score = max(0, min(deps_score, 100))

    # Testing (15%)
    test_score = 30  # base
    if "## Testing" in content or "test" in content_lower:
        test_score += 20
    if "pytest" in content_lower or "jest" in content_lower or "vitest" in content_lower:
        test_score += 15
    if "coverage" in content_lower:
        test_score += 15
    if "mock" in content_lower or "fixture" in content_lower:
        test_score += 10
    if "e2e" in content_lower or "integration" in content_lower:
        test_score += 10
    test_score = min(test_score, 100)

    overall = round(
        structure_score * 0.25
        + security_score * 0.25
        + ci_score * 0.15
        + deps_score * 0.20
        + test_score * 0.15
    )

    categories = {
        "structure": {
            "score": structure_score,
            "grade": _grade(structure_score),
            "label": "Project Structure",
            "details": "Architecture documentation, directory organization, coding standards",
        },
        "security": {
            "score": security_score,
            "grade": _grade(security_score),
            "label": "Security",
            "details": "Credential handling, input validation, vulnerability exposure",
        },
        "ci": {
            "score": ci_score,
            "grade": _grade(ci_score),
            "label": "CI/CD",
            "details": "Build pipelines, deployment workflows, linting automation",
        },
        "deps": {
            "score": deps_score,
            "grade": _grade(deps_score),
            "label": "Dependencies",
            "details": "Package documentation, known vulnerabilities, version management",
        },
        "testing": {
            "score": test_score,
            "grade": _grade(test_score),
            "label": "Testing",
            "details": "Test frameworks, coverage targets, test conventions",
        },
    }

    return {"overall": overall, "grade": _grade(overall), "categories": categories}


def _run_deep_scan(scan_id: str, repo_url: str) -> None:
    """Execute a deep scan with LLM analysis, dependency audit, scoring, and hygiene check."""
    import shutil
    import tempfile

    from anchormd.analyzers import run_all
    from anchormd.generators.composer import DocumentComposer
    from anchormd.models import ForgeConfig
    from anchormd.scanner import CodebaseScanner
    from web.generator import clone_repo, validate_github_url

    try:
        normalized_url = validate_github_url(repo_url)
    except ValueError as exc:
        _deep_scan_error(scan_id, str(exc))
        return

    tmp_dir = tempfile.mkdtemp(prefix="anchormd-deep-")
    clone_path = Path(tmp_dir) / "repo"

    tech_debt_signals: list[dict[str, Any]] = []
    compliance: dict[str, Any] = {}

    try:
        # Clone and generate CLAUDE.md
        clone_repo(normalized_url, clone_path)
        config = ForgeConfig(root_path=clone_path, max_files=5000)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()
        analyses = run_all(structure, config)
        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses)

        # Extract tech debt signals from analyzer results
        for analysis in analyses:
            findings = analysis.findings if hasattr(analysis, "findings") else {}
            if isinstance(findings, dict) and "signals" in findings:
                tech_debt_signals = findings["signals"]
                break

        # While clone is on disk: parse deps, build file tree, check compliance
        file_tree = _build_file_tree(clone_path)
        deps = _parse_dependencies(clone_path)
        compliance = _check_compliance(clone_path)
    except Exception as exc:
        logger.exception("Deep scan generation failed for %s", scan_id)
        _deep_scan_error(scan_id, f"Scan failed: {type(exc).__name__}: {exc}")
        return
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Run dependency audit (independent, can fail gracefully)
    dep_audit = _check_vulnerabilities(deps)

    # Run LLM analysis with tech debt context (independent, can fail gracefully)
    llm_result = _run_llm_analysis(content, file_tree, dep_audit, tech_debt_signals)

    # Compute category scores
    category_scores = _compute_category_scores(content, dep_audit.get("vulnerabilities", []))

    # Run context-hygiene on generated CLAUDE.md
    hygiene = _run_context_hygiene(content)

    # Check for previous scans of same repo (scan history)
    history = _get_scan_history(repo_url, scan_id)

    # Build enriched recommendations from LLM improvements
    recommendations = llm_result.get("improvements", []) if "error" not in llm_result else []

    # Build structured tech debt summary for report
    tech_debt_report = {
        "total_signals": len(tech_debt_signals),
        "critical": [s for s in tech_debt_signals if s.get("severity") == "critical"],
        "high": [s for s in tech_debt_signals if s.get("severity") == "high"],
        "medium": [s for s in tech_debt_signals if s.get("severity") == "medium"],
        "low": [s for s in tech_debt_signals if s.get("severity") == "low"],
    }

    # Assemble full report data
    report_data = {
        "llm_analysis": llm_result,
        "dependency_audit": dep_audit,
        "category_scores": category_scores,
        "recommendations": recommendations,
        "tech_debt": tech_debt_report,
        "compliance": compliance,
        "hygiene": hygiene,
        "history": history,
    }

    conn = _get_db()
    try:
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            UPDATE scans
            SET status = 'complete', content = ?, score = ?,
                files_scanned = ?, languages = ?, completed_at = ?,
                recommendations = ?
            WHERE scan_id = ?
            """,
            (
                content,
                category_scores["overall"],
                structure.total_files,
                json_module.dumps(structure.languages),
                now,
                json_module.dumps(report_data),
                scan_id,
            ),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed to update deep scan %s", scan_id)
    finally:
        conn.close()


def _deep_scan_error(scan_id: str, error_msg: str) -> None:
    """Mark a deep scan as failed."""
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE scans SET status = 'error', error = ?, completed_at = ? WHERE scan_id = ?",
            (error_msg, datetime.now(UTC).isoformat(), scan_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- API Routes: Stripe Checkout ---


@app.post("/api/checkout/deep-scan", response_model=CheckoutResponse)
@limiter.limit("5/minute")
async def create_deep_scan_checkout(
    request: Request,
    payload: CheckoutRequest,
) -> CheckoutResponse:
    """Create a Stripe Checkout session for a $19 deep scan."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    await _fetch_repo_metadata(payload.repo_url)

    # Pre-create the scan record so we have an ID for the success URL.
    scan_id = _make_scan_id(payload.repo_url)
    now = datetime.now(UTC).isoformat()

    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO scans (
                scan_id, repo_url, status, created_at, scan_type, email, repo_private
            )
            VALUES (?, ?, 'awaiting_payment', ?, 'deep', ?, ?)
            """,
            (scan_id, payload.repo_url, now, payload.email),
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
                                "AI-powered architecture review, dependency audit, "
                                "security analysis, and category scoring."
                            ),
                        },
                        "unit_amount": DEEP_SCAN_PRICE_CENTS,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            customer_email=payload.email,
            success_url=f"{SITE_URL}/?deep_scan={scan_id}",
            cancel_url=f"{SITE_URL}/",
            metadata={
                "product": "deep_scan",
                "repo_url": payload.repo_url,
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
        stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        print(f"Stripe webhook: invalid payload: {exc}")
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.SignatureVerificationError as exc:
        print(f"Stripe webhook: sig verify failed: {exc}")
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    # Parse raw payload as plain dict to avoid Stripe object access quirks
    import json as _wh_json

    event_dict = _wh_json.loads(payload)

    if event_dict["type"] == "checkout.session.completed":
        session = event_dict["data"]["object"]
        metadata = session.get("metadata") or {}

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
async def get_deep_scan_report(scan_id: str, request: Request) -> DeepScanReport:
    """Retrieve a deep scan report. Only available for paid deep scans."""
    user = await _get_current_user(request)
    row = _get_scan_row(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = _ensure_scan_access(row, user)

    if row_dict.get("scan_type") != "deep":
        raise HTTPException(status_code=403, detail="Deep scan report requires payment")

    languages_raw = row_dict.get("languages", "{}")
    try:
        languages = json_module.loads(languages_raw) if languages_raw else {}
    except (json_module.JSONDecodeError, TypeError):
        languages = {}

    recs_raw = row_dict.get("recommendations", "[]")
    try:
        report_data = json_module.loads(recs_raw) if recs_raw else {}
    except (json_module.JSONDecodeError, TypeError):
        report_data = {}

    # Support both old format (list) and new format (dict with nested sections)
    if isinstance(report_data, list):
        recommendations = report_data
        llm_analysis = None
        dependency_audit = None
        category_scores = None
        tech_debt = None
        compliance = None
        hygiene = None
        history = None
    else:
        recommendations = report_data.get("recommendations", [])
        llm_analysis = report_data.get("llm_analysis")
        dependency_audit = report_data.get("dependency_audit")
        category_scores = report_data.get("category_scores")
        tech_debt = report_data.get("tech_debt")
        compliance = report_data.get("compliance")
        hygiene = report_data.get("hygiene")
        history = report_data.get("history")

    return DeepScanReport(
        scan_id=row_dict["scan_id"],
        repo_url=row_dict["repo_url"],
        content=row_dict.get("content"),
        score=row_dict.get("score"),
        files_scanned=row_dict.get("files_scanned", 0),
        languages=languages,
        recommendations=recommendations,
        llm_analysis=llm_analysis,
        dependency_audit=dependency_audit,
        category_scores=category_scores,
        tech_debt=tech_debt,
        compliance=compliance,
        hygiene=hygiene,
        history=history,
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
    row = _get_scan_row(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = _ensure_scan_access(row, user)
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

    token = _gh_token_for(user)
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
    now = datetime.now(UTC)
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    conn = _get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

        unique_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM scans WHERE user_id IS NOT NULL"
        ).fetchone()[0]

        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        dau = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen_at IS NOT NULL AND last_seen_at >= ?",
            (day_ago,),
        ).fetchone()[0]

        wau = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen_at IS NOT NULL AND last_seen_at >= ?",
            (week_ago,),
        ).fetchone()[0]

        new_users_by_day = [
            {"date": r[0], "count": r[1]}
            for r in conn.execute(
                """
                SELECT DATE(created_at, 'unixepoch') as day, COUNT(*) as cnt
                FROM users
                WHERE created_at IS NOT NULL
                GROUP BY day ORDER BY day DESC LIMIT 30
                """
            ).fetchall()
        ]

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
        total_users=total_users,
        dau=dau,
        wau=wau,
        scans_by_day=scans_by_day,
        new_users_by_day=new_users_by_day,
        most_scanned_repos=most_scanned,
        average_score=avg_score,
        error_rate=error_rate,
        recent_scans=recent,
    )


@app.get("/api/scan/{scan_id}/fix-report")
async def get_fix_report(scan_id: str, request: Request) -> dict[str, Any]:
    """Generate a downloadable fix report with gap analysis and instructions."""
    import json
    import re

    user = await _get_current_user(request)
    row = _get_scan_row(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = _ensure_scan_access(row, user)
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
    depth_score = (
        (10 if line_count > 50 else 0)
        + (5 if line_count > 100 else 0)
        + (5 if line_count > 150 else 0)
    )
    code_score = 10 if code_block_count >= 2 else (5 if code_block_count >= 1 else 0)
    spec_score = 10 if bold_bullets > 5 else (5 if bold_bullets > 2 else 0)

    # --- Build fix actions sorted by point impact ---
    actions: list[dict[str, Any]] = []

    for heading in missing_headings:
        pts = round(60 / len(expected_headings))
        actions.append(
            {
                "priority": "high" if pts >= 6 else "medium",
                "action": f"Add `## {heading}` section",
                "points": pts,
                "category": "sections",
            }
        )

    if line_count <= 50:
        actions.append(
            {
                "priority": "high",
                "action": "Expand content to 150+ lines for full depth score (+20 pts)",
                "points": 20,
                "category": "depth",
            }
        )
    elif line_count <= 100:
        actions.append(
            {
                "priority": "medium",
                "action": "Expand content to 150+ lines (+10 pts remaining)",
                "points": 10,
                "category": "depth",
            }
        )
    elif line_count <= 150:
        actions.append(
            {
                "priority": "low",
                "action": "Expand content past 150 lines (+5 pts remaining)",
                "points": 5,
                "category": "depth",
            }
        )

    if code_block_count < 2:
        pts = 10 - code_score
        actions.append(
            {
                "priority": "medium",
                "action": f"Add code blocks (need {2 - code_block_count} more) for full code score",
                "points": pts,
                "category": "code_blocks",
            }
        )

    if bold_bullets <= 5:
        pts = 10 - spec_score
        actions.append(
            {
                "priority": "medium",
                "action": (
                    f"Add bold-label bullets (`- **Key**: value`) — need {6 - bold_bullets} more"
                ),
                "points": pts,
                "category": "specificity",
            }
        )

    actions.sort(key=lambda a: a["points"], reverse=True)

    # --- Section templates for missing headings ---
    section_templates = {
        "Project Overview": (
            "## Project Overview\n\n"
            "One-paragraph description of what this project does, who it's for, "
            "and its current maturity.\n\n"
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
    md += "\n---\n\n"

    # Score breakdown
    md += "## Score Breakdown\n\n"
    md += "| Category | Score | Max | Status |\n"
    md += "|----------|-------|-----|--------|\n"
    section_status = f"{len(present_headings)}/{len(expected_headings)} sections"
    md += f"| Section Coverage | {section_score} | 60 | {section_status} |\n"
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
        md += (
            "Add these sections to your CLAUDE.md to reach 100%. "
            "Fill in the bracketed placeholders.\n\n"
        )
        for heading in missing_headings:
            template = section_templates.get(heading, f"## {heading}\n\n[Add content here]\n")
            md += f"### Template: {heading}\n\n"
            md += f"```markdown\n{template}```\n\n"

    # Claude Code prompt
    md += "## Quick Fix — Claude Code Prompt\n\n"
    md += "Paste this into Claude Code to auto-generate the missing content:\n\n"
    md += "```\n"
    if missing_headings:
        sections_csv = ", ".join(missing_headings)
        md += f"Read my CLAUDE.md and add the following missing sections: {sections_csv}. "
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
    generated_date = datetime.now(UTC).strftime("%Y-%m-%d")
    md += f"*Generated by [anchormd](https://anchormd.dev) on {generated_date}*\n"

    return {
        "scan_id": scan_id,
        "repo_url": repo_url,
        "score": score,
        "points_to_100": points_to_100,
        "actions": actions,
        "missing_sections": missing_headings,
        "present_sections": present_headings,
        "breakdown": {
            "sections": {
                "score": section_score,
                "max": 60,
                "present": len(present_headings),
                "total": len(expected_headings),
            },
            "depth": {"score": depth_score, "max": 20, "lines": line_count},
            "code_blocks": {"score": code_score, "max": 10, "count": code_block_count},
            "specificity": {"score": spec_score, "max": 10, "bold_bullets": bold_bullets},
        },
        "markdown": md,
    }


@app.get("/api/scan/{scan_id}/cursorrules")
async def get_cursorrules(scan_id: str, request: Request) -> dict[str, Any]:
    """Convert a scan result to .cursorrules format for Cursor IDE."""
    import re

    user = await _get_current_user(request)
    row = _get_scan_row(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    row_dict = _ensure_scan_access(row, user)
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
        "Follow these rules strictly.\n\n" + content.strip() + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": cursorrules,
        "filename": ".cursorrules",
    }


@app.get("/api/scan/{scan_id}/copilot-instructions")
async def get_copilot_instructions(scan_id: str) -> dict[str, Any]:
    """Convert a scan result to GitHub Copilot's .github/copilot-instructions.md format."""
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
    content = re.sub(r"^# CLAUDE\.md — .+\n*", "", content)

    repo_url = row_dict["repo_url"]
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    instructions = (
        f"# Copilot Instructions — {repo_name}\n\n"
        "These are project instructions for GitHub Copilot. "
        "Apply them to every code suggestion, completion, and chat response in this repository.\n\n"
        + content.strip()
        + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": instructions,
        "filename": ".github/copilot-instructions.md",
    }


@app.get("/api/scan/{scan_id}/windsurfrules")
async def get_windsurfrules(scan_id: str) -> dict[str, Any]:
    """Convert a scan result to .windsurfrules format for Windsurf IDE."""
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
    content = re.sub(r"^# CLAUDE\.md — .+\n*", "", content)

    renames = {
        "## Project Overview": "## Project Context",
        "## Anti-Patterns": "## Avoid",
        "## Common Commands": "## Commands",
        "## Git Conventions": "## Git",
    }
    for old, new in renames.items():
        content = content.replace(old, new)

    repo_url = row_dict["repo_url"]
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    windsurfrules = (
        f"# Windsurf Rules — {repo_name}\n\n"
        "You are Cascade, an agentic AI coding assistant working on this project. "
        "Follow these rules strictly.\n\n" + content.strip() + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": windsurfrules,
        "filename": ".windsurfrules",
    }


def _load_scan_content(scan_id: str) -> tuple[str, str]:
    """Fetch a completed scan's content + repo name, or raise HTTPException."""
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

    repo_url = row_dict["repo_url"]
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    return row_dict["content"], repo_name


@app.get("/api/scan/{scan_id}/agents")
async def get_agents_md(scan_id: str) -> dict[str, Any]:
    """Convert a scan result to the AGENTS.md cross-tool convention.

    AGENTS.md is the shared convention adopted by Cursor, OpenAI Codex, and other
    AI coding tools — a single tool-agnostic instructions file per repo.
    """
    import re

    content, repo_name = _load_scan_content(scan_id)
    content = re.sub(r"^# CLAUDE\.md — .+\n*", "", content)

    agents_md = (
        f"# AGENTS.md — {repo_name}\n\n"
        "Instructions for AI coding agents working in this repository. "
        "Tool-agnostic: applies to Cursor, OpenAI Codex, Claude Code, Copilot, "
        "Windsurf, and any agent that honors AGENTS.md.\n\n" + content.strip() + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": agents_md,
        "filename": "AGENTS.md",
    }


@app.get("/api/scan/{scan_id}/codex")
async def get_codex_instructions(scan_id: str) -> dict[str, Any]:
    """Convert a scan result to an OpenAI Codex-flavored AGENTS.md.

    Codex reads AGENTS.md natively; this variant adds a Codex-targeted preamble.
    """
    import re

    content, repo_name = _load_scan_content(scan_id)
    content = re.sub(r"^# CLAUDE\.md — .+\n*", "", content)

    codex_md = (
        f"# AGENTS.md — {repo_name}\n\n"
        "You are OpenAI Codex operating on this repository. "
        "Follow these instructions for every edit, completion, and task. "
        "Prefer minimal diffs, stay within the conventions below, and run the "
        "project's test and lint commands before reporting work complete.\n\n"
        + content.strip()
        + "\n"
    )

    return {
        "scan_id": scan_id,
        "content": codex_md,
        "filename": "AGENTS.md",
    }


@app.get("/api/scan/{scan_id}/claude-md")
async def get_claude_md(scan_id: str) -> dict[str, Any]:
    """Return the raw generated CLAUDE.md for direct download."""
    content, _repo_name = _load_scan_content(scan_id)
    return {
        "scan_id": scan_id,
        "content": content,
        "filename": "CLAUDE.md",
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
