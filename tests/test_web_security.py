"""Security-focused tests for the web app."""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet, MultiFernet
from fastapi.testclient import TestClient

from web import app as web_app
from web.generator import _sanitize_clone_error


def _configure_test_db(tmp_path: Path) -> sqlite3.Connection:
    web_app.ADMIN_GITHUB_USERNAME = "octocat"
    if web_app._fernet is None:
        web_app._fernet = MultiFernet([Fernet(Fernet.generate_key())])
    web_app.DB_PATH = tmp_path / "scans.db"
    web_app._init_db()
    conn = web_app._get_db()
    conn.execute("DELETE FROM oauth_states")
    conn.execute("DELETE FROM scans")
    conn.execute("DELETE FROM users")
    conn.commit()
    return conn


def _insert_user(
    conn: sqlite3.Connection,
    github_id: int,
    username: str,
    session_token: str,
) -> None:
    encrypted = web_app._encrypt_token(f"gh-token-{github_id}")
    conn.execute(
        """
        INSERT INTO users (
            github_id, username, avatar_url, access_token, access_token_encrypted, created_at
        )
        VALUES (?, ?, '', NULL, ?, ?)
        """,
        (
            github_id,
            username,
            encrypted,
            time.time(),
        ),
    )
    row = conn.execute("SELECT id FROM users WHERE github_id = ?", (github_id,)).fetchone()
    assert row is not None
    user_id = row["id"]
    now = datetime.now(UTC)
    conn.execute(
        """
        INSERT INTO sessions (token_hash, user_id, created_at, last_used_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            web_app._hash_session_token(session_token),
            user_id,
            now.isoformat(),
            now.isoformat(),
            (now + timedelta(days=30)).isoformat(),
        ),
    )
    conn.commit()


def _insert_scan(
    conn: sqlite3.Connection,
    *,
    scan_id: str,
    repo_url: str,
    user_id: int | None,
    repo_private: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO scans (
            scan_id, repo_url, content, score, files_scanned, languages,
            status, created_at, completed_at, user_id, batch_id, repo_private, scan_type
        )
        VALUES (?, ?, 'generated', 88, 12, '{}', 'complete', ?, ?, ?, NULL, ?, 'free')
        """,
        (
            scan_id,
            repo_url,
            "2026-04-12T00:00:00+00:00",
            "2026-04-12T00:00:01+00:00",
            user_id,
            int(repo_private),
        ),
    )
    conn.commit()


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, timeout: float | None = None):
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:  # noqa: A002
        assert url.endswith("/login/oauth/access_token")
        assert json["code"] == "oauth-code"
        return _FakeResponse(200, {"access_token": "gho_secret_token"})

    async def get(self, url: str, headers: dict) -> _FakeResponse:
        assert url.endswith("/user")
        assert headers["Authorization"] == "Bearer gho_secret_token"
        return _FakeResponse(200, {"id": 101, "login": "octocat", "avatar_url": "https://avatar"})


def test_private_scan_requires_owning_session(tmp_path: Path) -> None:
    conn = _configure_test_db(tmp_path)
    try:
        _insert_user(conn, github_id=1, username="owner", session_token="owner-session")
        _insert_user(conn, github_id=2, username="other", session_token="other-session")
        _insert_scan(
            conn,
            scan_id="private123",
            repo_url="https://github.com/acme/private-repo",
            user_id=1,
            repo_private=True,
        )
    finally:
        conn.close()

    with TestClient(web_app.app) as client:
        assert client.get("/api/scan/private123").status_code == 403
        assert (
            client.get(
                "/api/scan/private123",
                headers={"Authorization": "Bearer other-session"},
            ).status_code
            == 403
        )

        response = client.get(
            "/api/scan/private123",
            headers={"Authorization": "Bearer owner-session"},
        )
        assert response.status_code == 200
        assert response.json()["repo_url"] == "https://github.com/acme/private-repo"


def test_public_scan_is_available_without_auth(tmp_path: Path) -> None:
    conn = _configure_test_db(tmp_path)
    try:
        _insert_scan(
            conn,
            scan_id="public123",
            repo_url="https://github.com/acme/public-repo",
            user_id=None,
            repo_private=False,
        )
    finally:
        conn.close()

    with TestClient(web_app.app) as client:
        response = client.get("/api/scan/public123")
        assert response.status_code == 200
        assert response.json()["repo_url"] == "https://github.com/acme/public-repo"


def test_cached_private_scan_is_not_reused_across_users(tmp_path: Path) -> None:
    conn = _configure_test_db(tmp_path)
    try:
        _insert_scan(
            conn,
            scan_id="private-cache",
            repo_url="https://github.com/acme/private-repo",
            user_id=7,
            repo_private=True,
        )
    finally:
        conn.close()

    assert (
        web_app._get_cached_free_scan("https://github.com/acme/private-repo", 7, True) is not None
    )
    assert web_app._get_cached_free_scan("https://github.com/acme/private-repo", 8, True) is None
    assert web_app._get_cached_free_scan("https://github.com/acme/private-repo", None, True) is None


def test_github_login_creates_state_and_callback_returns_app_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    conn = _configure_test_db(tmp_path)
    conn.close()
    monkeypatch.setattr(web_app, "GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setattr(web_app, "GITHUB_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(web_app.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(web_app.app) as client:
        login_response = client.get("/api/auth/github")
        assert login_response.status_code == 200

        oauth_url = login_response.json()["url"]
        params = parse_qs(urlparse(oauth_url).query)
        state = params["state"][0]

        conn = web_app._get_db()
        try:
            stored = conn.execute(
                "SELECT state FROM oauth_states WHERE state = ?",
                (state,),
            ).fetchone()
            assert stored is not None
        finally:
            conn.close()

        callback = client.get(f"/api/auth/callback?code=oauth-code&state={state}")
        assert callback.status_code == 200
        data = callback.json()
        assert data["token"] != "gho_secret_token"

        conn = web_app._get_db()
        try:
            user_row = conn.execute(
                "SELECT id, access_token, access_token_encrypted FROM users WHERE github_id = 101",
            ).fetchone()
            assert user_row is not None
            assert user_row["access_token"] is None
            assert web_app._decrypt_token(user_row["access_token_encrypted"]) == "gho_secret_token"
            session_row = conn.execute(
                "SELECT token_hash FROM sessions WHERE user_id = ?",
                (user_row["id"],),
            ).fetchone()
            assert session_row is not None
            assert session_row["token_hash"] == web_app._hash_session_token(data["token"])
        finally:
            conn.close()


def test_oauth_callback_rejects_invalid_state(tmp_path: Path) -> None:
    conn = _configure_test_db(tmp_path)
    conn.close()
    web_app.GITHUB_CLIENT_ID = "client-id"
    web_app.GITHUB_CLIENT_SECRET = "client-secret"

    with TestClient(web_app.app) as client:
        response = client.get("/api/auth/callback?code=oauth-code&state=missing")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid OAuth state"


def test_clone_errors_are_sanitized() -> None:
    stderr = (
        "fatal: could not read from "
        "https://x-access-token:secret-token@github.com/acme/private-repo.git"
    )
    cleaned = _sanitize_clone_error(
        stderr,
        "https://github.com/acme/private-repo.git",
        "secret-token",
    )
    assert "secret-token" not in cleaned
    assert "https://github.com/acme/private-repo.git" not in cleaned
    assert "[secure-token]" in cleaned
