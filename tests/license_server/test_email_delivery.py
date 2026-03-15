"""Tests for email delivery module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from license_server.email_delivery import _build_body, send_license_email


class TestBuildBody:
    """Tests for email body generation."""

    def test_contains_key(self):
        body = _build_body("ANMD-AB12-CD34-EF56", "pro")
        assert "ANMD-AB12-CD34-EF56" in body

    def test_contains_tier(self):
        body = _build_body("ANMD-AB12-CD34-EF56", "pro")
        assert "Pro" in body

    def test_contains_activation_instructions(self):
        body = _build_body("ANMD-AB12-CD34-EF56", "pro")
        assert "ANCHORMD_LICENSE" in body
        assert ".anchormd-license" in body


class TestSendLicenseEmail:
    """Tests for SMTP email sending."""

    def test_returns_false_when_smtp_not_configured(self, monkeypatch):
        monkeypatch.setattr("license_server.email_delivery.get_smtp_user", lambda: None)
        monkeypatch.setattr("license_server.email_delivery.get_smtp_password", lambda: None)

        result = send_license_email("test@example.com", "ANMD-AB12-CD34-EF56")
        assert result is False

    def test_returns_false_when_password_missing(self, monkeypatch):
        monkeypatch.setattr("license_server.email_delivery.get_smtp_user", lambda: "user")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_password", lambda: None)

        result = send_license_email("test@example.com", "ANMD-AB12-CD34-EF56")
        assert result is False

    def test_sends_email_on_success(self, monkeypatch):
        monkeypatch.setattr("license_server.email_delivery.get_smtp_user", lambda: "user")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_password", lambda: "pass")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_host", lambda: "localhost")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_port", lambda: 587)
        monkeypatch.setattr(
            "license_server.email_delivery.get_smtp_from", lambda: "noreply@test.com"
        )

        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("license_server.email_delivery.smtplib.SMTP", return_value=mock_smtp):
            result = send_license_email("test@example.com", "ANMD-AB12-CD34-EF56")

        assert result is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user", "pass")
        mock_smtp_instance.send_message.assert_called_once()

    def test_returns_false_on_smtp_error(self, monkeypatch):
        monkeypatch.setattr("license_server.email_delivery.get_smtp_user", lambda: "user")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_password", lambda: "pass")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_host", lambda: "localhost")
        monkeypatch.setattr("license_server.email_delivery.get_smtp_port", lambda: 587)

        with patch(
            "license_server.email_delivery.smtplib.SMTP",
            side_effect=ConnectionRefusedError("refused"),
        ):
            result = send_license_email("test@example.com", "ANMD-AB12-CD34-EF56")

        assert result is False
