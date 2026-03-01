"""Machine identification for license validation."""

from __future__ import annotations

import getpass
import hashlib
import platform


def get_machine_id() -> str:
    """Return a SHA-256 hex digest identifying this machine.

    Computed from hostname + username. Deterministic across sessions.
    No PII is transmitted — only the hash.
    """
    hostname = platform.node()
    username = getpass.getuser()
    raw = f"{hostname}:{username}"
    return hashlib.sha256(raw.encode()).hexdigest()
