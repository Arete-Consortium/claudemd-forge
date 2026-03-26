"""Feature gating decorators and helpers for AnchorMD."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import typer
from rich.console import Console

from anchormd.licensing import (
    PRO_PRESETS,
    Tier,
    check_scan_quota,
    get_license_info,
    get_upgrade_message,
    has_feature,
    has_preset_access,
    is_known_preset,
    record_scan,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def require_pro(feature: str) -> Callable[[F], F]:
    """Decorator that gates a CLI command behind Pro tier.

    If the user does not have a valid Pro license, prints an upgrade
    message and exits with code 1 instead of running the command.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not has_feature(feature):
                from anchormd.telemetry import track_pro_gate

                track_pro_gate(feature)
                console = Console()
                console.print(f"[yellow]{get_upgrade_message(feature)}[/yellow]")
                raise typer.Exit(1)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def require_quota(scan_type: str = "deep_scan") -> Callable[[F], F]:
    """Decorator that checks scan quota before running a command.

    If the user has exceeded their tier's scan limit, prints a message
    and exits. Fails open if the server is unavailable.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            quota = check_scan_quota(scan_type)
            if quota is not None and not quota.get("allowed", True):
                console = Console()
                used = quota.get("used", 0)
                limit = quota.get("limit", 0)
                period = quota.get("period", "this month")
                console.print(
                    f"[yellow]Scan quota reached: {used}/{limit} {scan_type}s "
                    f"used in {period}.[/yellow]"
                )
                console.print(
                    "[dim]Upgrade your plan or wait for the next billing period: "
                    "https://anchormd.dev/pro[/dim]"
                )
                raise typer.Exit(1)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def record_scan_usage(scan_type: str = "deep_scan", repo_fingerprint: str | None = None) -> None:
    """Record a scan after successful execution. Fire-and-forget."""
    result = record_scan(scan_type, repo_fingerprint)
    if result and not result.get("allowed", True):
        logger.warning("Scan recorded but quota now exhausted: %s", result)


def check_preset_access(preset_name: str) -> None:
    """Raise typer.Exit if the preset is unknown or requires Pro.

    Call this before applying a preset in generate/init commands.
    Distinguishes between "preset doesn't exist" and "preset requires
    a higher tier" so users get actionable error messages.
    """
    if not is_known_preset(preset_name):
        console = Console()
        console.print(f"[red]Preset '{preset_name}' not found.[/red]")
        console.print("[dim]Run 'anchormd presets' to see available presets.[/dim]")
        raise typer.Exit(1)

    if not has_preset_access(preset_name):
        console = Console()
        console.print(f"[yellow]Preset '{preset_name}' requires AnchorMD Pro.[/yellow]")
        console.print(
            "[dim]Upgrade to Pro for premium presets: https://anchormd.dev/pro[/dim]"
        )
        raise typer.Exit(1)


def get_available_presets() -> dict[str, str]:
    """Return preset names and their access status for display.

    Returns a dict mapping preset name to either "free" or "pro".
    """
    result: dict[str, str] = {}
    info = get_license_info()

    # Import here to avoid circular imports.
    from anchormd.templates.frameworks import (
        FRAMEWORK_PRESETS,
        PREMIUM_PRESETS,
    )
    from anchormd.templates.presets import PRESET_PACKS

    for name in PRESET_PACKS:
        if name in PRO_PRESETS:
            result[name] = "unlocked" if info.tier == Tier.PRO else "pro"
        else:
            result[name] = "free"

    for name in FRAMEWORK_PRESETS:
        if name in PRO_PRESETS:
            result[name] = "unlocked" if info.tier == Tier.PRO else "pro"
        else:
            result[name] = "free"

    for name in PREMIUM_PRESETS:
        if name in PRO_PRESETS:
            result[name] = "unlocked" if info.tier == Tier.PRO else "pro"
        else:
            result[name] = "free"

    return result
