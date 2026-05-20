"""reelax CLI — Auto-scroll Instagram Reels while you code."""

import os
import subprocess
import sys


# Fix Windows terminal encoding for Unicode symbols
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import click
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reelax import __version__
from reelax.core.config import (
    ReelaxConfig,
    load_config,
    save_config,
    get_default_config_yaml,
    CONFIG_FILE,
)
from reelax.core.scroller import ScrollEngine, ScrollConfig, ScrollSession, Cadence, CADENCE_INTERVALS
from reelax.core.exceptions import (
    DeviceNotFoundError,
    ADBNotInstalledError,
    ReelaxError,
)

console = Console(force_terminal=True)

# --- Configure loguru ---
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}",
    level="INFO",
)


# ──────────────────────────────────────────────
#  Banner
# ──────────────────────────────────────────────

BANNER = r"""
[bold green]
                  _            
  _ __ ___  ___ | | __ ___  __
 | '__/ _ \/ _ \| |/ _` \ \/ /
 | | |  __/  __/| | (_| |>  < 
 |_|  \___|\___|_|\__,_/_/\_\
[/bold green]
[dim] Auto-scroll Reels while you code. v{version}[/dim]
"""


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _build_session_panel(session: ScrollSession, paused: bool) -> Panel:
    """Build a Rich panel showing live session stats."""
    status = "[bold yellow]⏸  PAUSED (typing)[/bold yellow]" if paused else "[bold green]▶  SCROLLING[/bold green]"
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=18)
    table.add_column()
    table.add_row("Status", status)
    table.add_row("Session time", session.elapsed_display)
    table.add_row("Reels scrolled", str(session.reels_scrolled))
    table.add_row("Typing pauses", str(session.pauses))
    return Panel(table, title="[bold]Live Session[/bold]", border_style="green" if not paused else "yellow")


# ──────────────────────────────────────────────
#  CLI Group
# ──────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="reelax")
@click.pass_context
def main(ctx):
    """reelax — Auto-scroll Instagram Reels while you code."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ──────────────────────────────────────────────
#  reelax start
# ──────────────────────────────────────────────

@main.command()
@click.option("--device", "-d", default=None, help="Device serial (default: auto-detect)")
@click.option("--interval", "-i", default=None, type=float, help="Seconds between scrolls")
@click.option("--cadence", "-c", type=click.Choice(["slow", "medium", "fast"]), default=None, help="Scroll speed preset (slow=30s, medium=20s, fast=8s)")
@click.option("--idle", default=None, type=float, help="Seconds of no typing before resuming (default: 3)")
@click.option("--wifi", "-w", default=None, help="Connect via WiFi ADB (e.g. 192.168.1.5:5555)")
@click.option("--no-keyboard", is_flag=True, help="Disable keyboard detection (always scroll)")
def start(device: str | None, interval: float | None, cadence: str | None, idle: float | None, wifi: str | None, no_keyboard: bool):
    """Start scrolling Reels on your connected Android device."""
    console.print(BANNER.format(version=__version__))

    # Load config, then override with CLI flags
    user_config = load_config()

    # Resolve interval: CLI flag > cadence preset > config file
    if interval:
        resolved_interval = interval
    elif cadence:
        resolved_interval = CADENCE_INTERVALS[Cadence(cadence)]
    else:
        resolved_interval = user_config.scroll.interval_seconds

    scroll_config = ScrollConfig(
        interval_seconds=resolved_interval,
        idle_threshold_seconds=idle or user_config.keyboard.idle_threshold_seconds,
        ad_skip_enabled=user_config.scroll.ad_skip_enabled,
        blocklist_keywords=user_config.scroll.blocklist_keywords,
    )

    # Resolve device serial
    if wifi:
        serial_display = f"WiFi ({wifi})"
    elif device:
        serial_display = device
    elif user_config.device.serial != "auto":
        serial_display = user_config.device.serial
    else:
        serial_display = "auto-detect"

    serial = device if device else (None if user_config.device.serial == "auto" else user_config.device.serial)

    # Resolve cadence display
    cadence_display = cadence or "medium"
    if interval:
        cadence_display = f"custom ({interval}s)"

    # Show session info
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column(style="bold cyan", width=18)
    info_table.add_column()
    info_table.add_row("Device", serial_display)
    info_table.add_row("Cadence", cadence_display)
    info_table.add_row("Scroll interval", f"{scroll_config.interval_seconds}s")
    info_table.add_row("Idle threshold", f"{scroll_config.idle_threshold_seconds}s")
    info_table.add_row("Keyboard pause", "[red]OFF[/red]" if no_keyboard else "[green]ON[/green]")
    console.print(Panel(info_table, title="[bold]Session Config[/bold]", border_style="green"))
    console.print()

    try:
        engine = ScrollEngine(config=scroll_config)

        if no_keyboard:
            scroll_config.idle_threshold_seconds = 0

        # WiFi connection
        if wifi:
            from reelax.core.adb import connect_wifi
            engine.device = connect_wifi(wifi)
            console.print(f"[bold green]✔ Connected via WiFi:[/bold green] {wifi}")
        
        console.print("[bold green]▶ Starting scroll session...[/bold green]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]\n")
        engine.start(serial=serial if not wifi else None)

    except DeviceNotFoundError as e:
        console.print(f"\n[bold red]✖ Device Error[/bold red]\n{e}")
        sys.exit(1)
    except ADBNotInstalledError as e:
        console.print(f"\n[bold red]✖ ADB Not Found[/bold red]\n{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⏹ Session stopped by user.[/bold yellow]")
        if hasattr(engine, 'session'):
            _print_session_summary_rich(engine.session)
    except ReelaxError as e:
        console.print(f"\n[bold red]✖ Error[/bold red]\n{e}")
        sys.exit(1)


def _print_session_summary_rich(session: ScrollSession) -> None:
    """Print a beautiful session summary using Rich."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=18)
    table.add_column()
    table.add_row("Duration", session.elapsed_display)
    table.add_row("Reels scrolled", str(session.reels_scrolled))
    table.add_row("Typing pauses", str(session.pauses))
    console.print()
    console.print(Panel(table, title="[bold]Session Summary[/bold]", border_style="cyan"))


# ──────────────────────────────────────────────
#  reelax devices
# ──────────────────────────────────────────────

@main.command()
def devices():
    """List connected Android devices."""
    from reelax.core.adb import list_devices as _list_devices

    console.print(BANNER.format(version=__version__))

    try:
        found = _list_devices()
        if not found:
            console.print("[yellow]No devices found.[/yellow]")
            console.print("[dim]Make sure USB Debugging is enabled and your phone is connected.[/dim]")
            return

        table = Table(title="Connected Devices", border_style="green")
        table.add_column("#", style="bold cyan", width=4)
        table.add_column("Serial", style="bold white")
        for i, serial in enumerate(found, 1):
            table.add_row(str(i), serial)
        console.print(table)

    except ADBNotInstalledError as e:
        console.print(f"[bold red]✖ ADB Not Found[/bold red]\n{e}")
        sys.exit(1)


# ──────────────────────────────────────────────
#  reelax config
# ──────────────────────────────────────────────

@main.command("config")
@click.option("--show", is_flag=True, help="Print the current config to terminal")
@click.option("--reset", is_flag=True, help="Reset config to defaults")
def config_cmd(show: bool, reset: bool):
    """View or manage the reelax config file."""
    console.print(BANNER.format(version=__version__))

    if reset:
        save_config(ReelaxConfig())
        console.print("[bold green]✔ Config reset to defaults.[/bold green]")
        console.print(f"[dim]Saved to {CONFIG_FILE}[/dim]")
        return

    if show:
        cfg = load_config()
        console.print(Panel(
            get_default_config_yaml() if not CONFIG_FILE.exists() else open(CONFIG_FILE).read(),
            title=f"[bold]{CONFIG_FILE}[/bold]",
            border_style="cyan",
        ))
        return

    # Default: open config in editor, creating it if it doesn't exist
    if not CONFIG_FILE.exists():
        save_config(ReelaxConfig())
        console.print(f"[green]Created default config at {CONFIG_FILE}[/green]")

    # Try to open in the user's default editor
    try:
        click.edit(filename=str(CONFIG_FILE))
    except click.UsageError:
        console.print(f"[yellow]Could not open editor. Edit manually:[/yellow]\n  {CONFIG_FILE}")


# ──────────────────────────────────────────────
#  reelax doctor
# ──────────────────────────────────────────────

@main.command()
def doctor():
    """Diagnose your setup: ADB, device, and Instagram status."""
    console.print(BANNER.format(version=__version__))
    console.print("[bold]Running diagnostics...[/bold]\n")

    all_good = True

    # Check 1: ADB installed
    try:
        result = subprocess.run(["adb", "version"], capture_output=True, text=True)
        version_line = result.stdout.strip().split("\n")[0]
        console.print(f"  [bold green]✔[/bold green] ADB installed — {version_line}")
    except FileNotFoundError:
        console.print("  [bold red]✖[/bold red] ADB not found in PATH")
        console.print("    [dim]Install: https://developer.android.com/tools/releases/platform-tools[/dim]")
        all_good = False

    # Check 2: Device connected
    try:
        from reelax.core.adb import list_devices as _list_devices
        found = _list_devices()
        if found:
            for serial in found:
                console.print(f"  [bold green]✔[/bold green] Device connected — {serial}")
        else:
            console.print("  [bold red]✖[/bold red] No Android device detected")
            console.print("    [dim]Connect via USB and enable USB Debugging in Developer Options.[/dim]")
            all_good = False
    except ADBNotInstalledError:
        console.print("  [bold red]✖[/bold red] Cannot check devices (ADB missing)")
        all_good = False

    # Check 3: Instagram installed on device
    if all_good:
        try:
            from reelax.core.adb import list_devices as _list_devices
            serial = _list_devices()[0]
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "pm", "list", "packages", "com.instagram.android"],
                capture_output=True, text=True,
            )
            if "com.instagram.android" in result.stdout:
                console.print("  [bold green]✔[/bold green] Instagram is installed on device")
            else:
                console.print("  [bold yellow]⚠[/bold yellow] Instagram not found on device")
                console.print("    [dim]Install Instagram from the Play Store.[/dim]")
                all_good = False
        except Exception:
            console.print("  [bold yellow]⚠[/bold yellow] Could not check Instagram status")

    # Check 4: Config file
    if CONFIG_FILE.exists():
        console.print(f"  [bold green]✔[/bold green] Config file exists — {CONFIG_FILE}")
    else:
        console.print(f"  [bold yellow]⚠[/bold yellow] No config file (will use defaults)")
        console.print(f"    [dim]Run `reelax config --reset` to create one.[/dim]")

    # Summary
    console.print()
    if all_good:
        console.print(Panel("[bold green]All checks passed! You're ready to reelax.[/bold green]", border_style="green"))
    else:
        console.print(Panel("[bold yellow]Some issues found. Fix them above and run `reelax doctor` again.[/bold yellow]", border_style="yellow"))


# ──────────────────────────────────────────────
#  reelax status
# ──────────────────────────────────────────────

@main.command()
def status():
    """Show current session info (if running)."""
    console.print(BANNER.format(version=__version__))
    console.print("[dim]No active session. Run `reelax start` to begin.[/dim]")


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    main()
