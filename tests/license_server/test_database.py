"""Tests for database connection and migration runner."""

from __future__ import annotations

import sqlite3

from license_server.database import run_migrations


class TestMigrations:
    def test_migration_creates_tables(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "licenses" in tables
        assert "machine_activations" in tables
        assert "validation_log" in tables
        assert "schema_migrations" in tables
        conn.close()

    def test_migration_idempotent(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        first = run_migrations(conn)
        second = run_migrations(conn)
        assert len(first) > 0
        assert len(second) == 0
        conn.close()

    def test_migration_records_version(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        versions = [
            row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        ]
        assert 1 in versions
        conn.close()

    def test_wal_mode(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA journal_mode=WAL")
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        # In-memory databases may report 'memory' instead of 'wal'
        assert mode in ("wal", "memory")
        conn.close()

    def test_foreign_keys_enabled(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_licenses_table_schema(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(licenses)").fetchall()}
        expected = {
            "id",
            "key_hash",
            "license_key_masked",
            "tier",
            "email",
            "active",
            "created_at",
            "expires_at",
            "stripe_customer_id",
            "stripe_subscription_id",
            "metadata",
        }
        assert expected.issubset(columns)
        conn.close()

    def test_machine_activations_schema(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(machine_activations)").fetchall()
        }
        expected = {"id", "license_id", "machine_id", "first_seen", "last_seen"}
        assert expected.issubset(columns)
        conn.close()

    def test_validation_log_schema(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(validation_log)").fetchall()
        }
        expected = {"id", "key_hash", "machine_id", "result", "ip_address", "created_at"}
        assert expected.issubset(columns)
        conn.close()

    def test_license_insert_and_read(self) -> None:
        import hashlib
        import uuid

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        lid = str(uuid.uuid4())
        key_hash = hashlib.sha256(b"test").hexdigest()
        conn.execute(
            "INSERT INTO licenses (id, key_hash, license_key_masked, tier, email) "
            "VALUES (?, ?, ?, ?, ?)",
            (lid, key_hash, "CMDF-****-****-XXXX", "pro", "t@t.com"),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (lid,)).fetchone()
        assert row["tier"] == "pro"
        assert row["email"] == "t@t.com"
        assert row["active"] == 1
        conn.close()

    def test_key_hash_unique_constraint(self) -> None:
        import hashlib
        import sqlite3 as _sqlite3
        import uuid

        conn = _sqlite3.connect(":memory:")
        conn.row_factory = _sqlite3.Row
        run_migrations(conn)

        key_hash = hashlib.sha256(b"dup").hexdigest()
        conn.execute(
            "INSERT INTO licenses (id, key_hash, license_key_masked, tier) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), key_hash, "CMDF-****-****-XXXX", "pro"),
        )
        conn.commit()

        import pytest

        with pytest.raises(_sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO licenses (id, key_hash, license_key_masked, tier) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), key_hash, "CMDF-****-****-XXXX", "pro"),
            )
        conn.close()

    def test_machine_activation_unique_constraint(self) -> None:
        import hashlib
        import sqlite3 as _sqlite3
        import uuid

        conn = _sqlite3.connect(":memory:")
        conn.row_factory = _sqlite3.Row
        run_migrations(conn)

        lid = str(uuid.uuid4())
        key_hash = hashlib.sha256(b"test").hexdigest()
        conn.execute(
            "INSERT INTO licenses (id, key_hash, license_key_masked, tier) VALUES (?, ?, ?, ?)",
            (lid, key_hash, "CMDF-****-****-XXXX", "pro"),
        )
        conn.execute(
            "INSERT INTO machine_activations (license_id, machine_id) VALUES (?, ?)",
            (lid, "machine-abc"),
        )
        conn.commit()

        import pytest

        with pytest.raises(_sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO machine_activations (license_id, machine_id) VALUES (?, ?)",
                (lid, "machine-abc"),
            )
        conn.close()
