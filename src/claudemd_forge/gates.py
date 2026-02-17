"""Feature gating decorators and helpers for ClaudeMD Forge."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import typer
from rich.console import Console

from claudemd_forge.licensing import (
    PRO_PRESETS,
    Tier,
    get_license_info,
    get_upgrade_message,
    has_feature,
    has_preset_access,
    is_known_preset,
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
                console = Console()
                console.print(f"[yellow]{get_upgrade_message(feature)}[/yellow]")
                raise typer.Exit(1)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def check_preset_access(preset_name: str) -> None:
    """Raise typer.Exit if the preset is unknown or requires Pro.

    Call this before applying a preset in generate/init commands.
    Distinguishes between "preset doesn't exist" and "preset requires
    a higher tier" so users get actionable error messages.
    """
    if not is_known_preset(preset_name):
        console = Console()
        console.print(f"[red]Preset '{preset_name}' not found.[/red]")
        console.print("[dim]Run 'claudemd-forge presets' to see available presets.[/dim]")
        raise typer.Exit(1)

    if not has_preset_access(preset_name):
        console = Console()
        console.print(f"[yellow]Preset '{preset_name}' requires ClaudeMD Forge Pro.[/yellow]")
        console.print(
            "[dim]Upgrade to Pro for premium presets: https://claudemd-forge.dev/pro[/dim]"
        )
        raise typer.Exit(1)


def get_available_presets() -> dict[str, str]:
    """Return preset names and their access status for display.

    Returns a dict mapping preset name to either "free" or "pro".
    """
    result: dict[str, str] = {}
    info = get_license_info()

    # Import here to avoid circular imports.
    from claudemd_forge.templates.frameworks import (
        FRAMEWORK_PRESETS,
        PREMIUM_PRESETS,
    )
    from claudemd_forge.templates.presets import PRESET_PACKS

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
