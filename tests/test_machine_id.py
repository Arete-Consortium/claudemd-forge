"""Tests for machine identification."""

from __future__ import annotations

from unittest.mock import patch

from anchormd.machine_id import get_machine_id


class TestMachineId:
    def test_returns_string(self) -> None:
        mid = get_machine_id()
        assert isinstance(mid, str)

    def test_hex_format(self) -> None:
        mid = get_machine_id()
        int(mid, 16)  # Raises ValueError if not hex

    def test_64_chars(self) -> None:
        mid = get_machine_id()
        assert len(mid) == 64

    def test_deterministic(self) -> None:
        m1 = get_machine_id()
        m2 = get_machine_id()
        assert m1 == m2

    def test_no_pii_in_output(self) -> None:
        with (
            patch("anchormd.machine_id.platform.node", return_value="my-host"),
            patch("anchormd.machine_id.getpass.getuser", return_value="my-user"),
        ):
            mid = get_machine_id()
            assert "my-host" not in mid
            assert "my-user" not in mid

    def test_different_hosts_different_ids(self) -> None:
        with patch("anchormd.machine_id.platform.node", return_value="host-a"):
            m1 = get_machine_id()
        with patch("anchormd.machine_id.platform.node", return_value="host-b"):
            m2 = get_machine_id()
        assert m1 != m2

    def test_different_users_different_ids(self) -> None:
        with patch("anchormd.machine_id.getpass.getuser", return_value="alice"):
            m1 = get_machine_id()
        with patch("anchormd.machine_id.getpass.getuser", return_value="bob"):
            m2 = get_machine_id()
        assert m1 != m2
