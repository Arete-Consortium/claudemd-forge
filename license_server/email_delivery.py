"""Email delivery for license keys via SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from license_server.config import (
    get_smtp_from,
    get_smtp_host,
    get_smtp_password,
    get_smtp_port,
    get_smtp_user,
)

logger = logging.getLogger(__name__)

# Product display names and env var names for activation instructions
PRODUCT_INFO: dict[str, dict[str, str]] = {
    "claudemd-forge": {
        "display": "ClaudeMD Forge",
        "env_var": "CLAUDEMD_FORGE_LICENSE",
        "file": "~/.claudemd-forge-license",
        "issues": "https://github.com/Arete-Consortium/claudemd-forge/issues",
    },
    "agent-lint": {
        "display": "Agent Lint",
        "env_var": "AGENT_LINT_LICENSE",
        "file": "~/.agent-lint-license",
        "issues": "https://github.com/AreteDriver/agent-lint/issues",
    },
    "ai-spend": {
        "display": "AI Spend",
        "env_var": "AI_SPEND_LICENSE",
        "file": "~/.ai-spend-license",
        "issues": "https://github.com/AreteDriver/ai-spend/issues",
    },
    "promptctl": {
        "display": "PromptCTL",
        "env_var": "PROMPTCTL_LICENSE",
        "file": "~/.promptctl-license",
        "issues": "https://github.com/AreteDriver/promptctl/issues",
    },
    "context-hygiene": {
        "display": "Context Hygiene",
        "env_var": "CONTEXT_HYGIENE_LICENSE",
        "file": "~/.context-hygiene-license",
        "issues": "https://github.com/AreteDriver/context-hygiene/issues",
    },
}


def send_license_email(
    email: str, license_key: str, tier: str = "pro", product: str = "claudemd-forge"
) -> bool:
    """Send a license key to the customer via SMTP.

    Returns True on success, False on failure (never raises).
    """
    smtp_user = get_smtp_user()
    smtp_password = get_smtp_password()

    if not smtp_user or not smtp_password:
        logger.warning("SMTP not configured — skipping email to %s", email)
        return False

    info = PRODUCT_INFO.get(product, PRODUCT_INFO["claudemd-forge"])

    msg = EmailMessage()
    msg["Subject"] = f"Your {info['display']} {tier.title()} License Key"
    msg["From"] = get_smtp_from()
    msg["To"] = email
    msg.set_content(_build_body(license_key, tier, product))

    try:
        with smtplib.SMTP(get_smtp_host(), get_smtp_port(), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("License key emailed to %s for %s", email, product)
        return True
    except Exception:
        logger.exception("Failed to email license key to %s", email)
        return False


def send_bundle_email(
    email: str,
    licenses: list[tuple[str, str]],
    tier: str = "pro",
    bundle_id: str | None = None,
) -> bool:
    """Send multiple license keys in a single email.

    licenses: list of (product, plaintext_key) tuples.
    Returns True on success, False on failure (never raises).
    """
    smtp_user = get_smtp_user()
    smtp_password = get_smtp_password()

    if not smtp_user or not smtp_password:
        logger.warning("SMTP not configured — skipping bundle email to %s", email)
        return False

    msg = EmailMessage()
    msg["Subject"] = f"Your Pro Bundle License Keys ({len(licenses)} products)"
    msg["From"] = get_smtp_from()
    msg["To"] = email
    msg.set_content(_build_bundle_body(licenses, tier, bundle_id))

    try:
        with smtplib.SMTP(get_smtp_host(), get_smtp_port(), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("Bundle email sent to %s (%d keys)", email, len(licenses))
        return True
    except Exception:
        logger.exception("Failed to email bundle keys to %s", email)
        return False


def _build_bundle_body(
    licenses: list[tuple[str, str]], tier: str, bundle_id: str | None = None
) -> str:
    """Build the plain-text email body for a bundle purchase."""
    lines = [f"Thanks for purchasing the Pro Bundle ({tier.title()})!\n"]
    lines.append(f"Bundle ID: {bundle_id or 'N/A'}\n")
    lines.append("Your license keys:\n")

    for product, key in licenses:
        info = PRODUCT_INFO.get(product, PRODUCT_INFO["claudemd-forge"])
        lines.append(f"  {info['display']}:")
        lines.append(f"    Key: {key}")
        lines.append(f'    Activate: export {info["env_var"]}="{key}"')
        lines.append(f'    Or save: echo "{key}" > {info["file"]}\n')

    lines.append("These keys are shown once — save them somewhere safe.\n")
    lines.append("If you have questions, reply to this email.\n")
    lines.append("— Arete Consortium")
    return "\n".join(lines)


def _build_body(license_key: str, tier: str, product: str = "claudemd-forge") -> str:
    """Build the plain-text email body."""
    info = PRODUCT_INFO.get(product, PRODUCT_INFO["claudemd-forge"])
    return f"""Thanks for purchasing {info["display"]} {tier.title()}!

Your license key:

    {license_key}

To activate, set the environment variable:

    export {info["env_var"]}="{license_key}"

Or save it to a file:

    echo "{license_key}" > {info["file"]}

This key is shown once — save it somewhere safe.

If you have questions, reply to this email or open an issue:
{info["issues"]}

— Arete Consortium
"""
