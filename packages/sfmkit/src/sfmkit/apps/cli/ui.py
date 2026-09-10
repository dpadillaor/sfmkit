"""The `sfmkit ui` command."""

from __future__ import annotations

from sfmkit.apps.cli._common import console


def cmd_ui(args) -> int:
    """Browse and compare runs in a terminal interface."""
    try:
        from sfmkit.apps.tui import run as run_tui
    except ImportError:
        console.print("[red]the TUI needs textual:[/red] pip install 'sfmkit[tui]'")
        return 1
    run_tui(args.runs)
    return 0
