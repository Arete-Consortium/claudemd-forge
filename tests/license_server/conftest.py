"""Shared fixtures for license server tests."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from license_server import main as main_module
from license_server.database import run_migrations
from license_server.main import app


@pytest.fixture
def db(tmp_path):
    """In-memory SQLite database with migrations applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn)
    return conn


@pytest.fixture
def client(db, monkeypatch):
    """TestClient wired to the in-memory database."""
    monkeypatch.setattr(main_module, "_db_path_override", ":memory:")

    # Override get_connection to always return our test db
    def _get_test_conn(db_path=None):
        return db

    monkeypatch.setattr("license_server.main.get_connection", _get_test_conn)
    monkeypatch.setattr("license_server.database._connection", db)

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token():
    """Default admin bearer token for testing."""
    return "change-me-in-production"
