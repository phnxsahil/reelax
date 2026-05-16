"""reelax Interactive Dashboard — The main experience."""

import os
import subprocess
import sys
import time
import threading
from typing import Optional

# Fix Windows terminal encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich import box
from loguru import logger

from reelax import __version__
from reelax.core.adb import list_devices, connect_device, connect_wifi, ADBDevice
from reelax.core.scroller import ScrollEngine, ScrollConfig, Cadence, CADENCE_INTERVALS
from reelax.core.config import load_config, save_config, ReelaxConfig, CONFIG_FILE
from reelax.core.exceptions import DeviceNotFoundError, ADBNotInstalledError

console = Console(force_terminal=True)

# Suppress loguru during dashboard mode
logger.remove()


# ──────────────────────────────────────────────
#  ASCII Art & Branding
# ──────────────────────────────────────────────

LOGO = r"""
                  _            
  _ __ ___  ___ | | __ ___  __
 | '__/ _ \/ _ \| |/ _` \ \/ /
 | | |  __/  __/| | (_| |>  < 
 |_|  \___|\___|_|\__,_/_/\_\
"""


# ──────────────────────────────────────────────
#  scrcpy Manager — Small, Pinned, Always-on-Top
# ──────────────────────────────────────────────

class ScrcpyManager:
    """Manages the scrcpy screen mirroring process."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None

    @staticmethod
    def is_installed() -> bool:
        try:
            result = subprocess.run(["scrcpy", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def start(self, serial: str, title: str = "reelax") -> bool:
        """Launch scrcpy as a small, pinned, always-on-top window."""
        if self._process and self._process.poll() is None:
            return True

        try:
            self._process = subprocess.Popen(
                [
                    "scrcpy",
                    "-s", serial,
                    "--window-title", title,
                    "--window-width", "280",       # Small compact window
                    "--window-height", "600",
                    "--window-x", "50",             # Position: top-left area
                    "--window-y", "50",
                    "--always-on-top",              # Pinned above everything
                    "--stay-awake",                 # Keep phone awake
                    "--turn-screen-off",            # Turn off phone screen (saves battery)
                    "--power-off-on-close",         # Turn off phone screen when scrcpy closes
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            return False

    def stop(self):
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None


# ──────────────────────────────────────────────
#  Non-blocking key reader (Cross-platform)
# ──────────────────────────────────────────────

if sys.platform == "win32":
    import msvcrt
    def get_pressed_key() -> Optional[str]:
        """Check if a key was pressed (non-blocking Windows)."""
        if msvcrt.kbhit():
            key = msvcrt.getch()
            try:
                return key.decode("utf-8").lower()
            except UnicodeDecodeError:
                return None
        return None
else:
    import select
    import tty
    import termios
    def get_pressed_key() -> Optional[str]:
        """Check if a key was pressed (non-blocking Unix)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if rlist:
                key = sys.stdin.read(1)
                return key.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None


# ──────────────────────────────────────────────
#  Live Dashboard Renderer
# ──────────────────────────────────────────────

def build_dashboard(engine: ScrollEngine, scrcpy: ScrcpyManager, show_help: bool = False) -> Panel:
    """Build the live dashboard panel with stats and inline commands."""
    session = engine.session

    # Status based on engine state
    status_map = {
        "paused": Text("⏸  PAUSED — you're typing", style="bold yellow"),
        "scrolling": Text("▶  SCROLLING", style="bold green"),
        "ad_skip": Text("⚡ SKIPPING AD", style="bold red"),
        "keyword_skip": Text("🛑 FILTERED KEYWORD", style="bold red"),
        "recovering": Text("↩  RECOVERING — returning to Reels", style="bold magenta"),
        "idle": Text("▶  READY", style="bold green"),
    }
    status_text = status_map.get(engine.last_status, status_map["idle"])

    # Main stats table
    stats = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    stats.add_column(style="bold cyan", width=20)
    stats.add_column()

    stats.add_row("Status", status_text)
    stats.add_row("", "")
    stats.add_row("Session time", session.elapsed_display)
    stats.add_row("Reels scrolled", str(session.reels_scrolled))
    stats.add_row("Ads skipped", str(session.ads_skipped))
    stats.add_row("Keywords blocked", str(session.keywords_filtered))
    stats.add_row("Auto-recoveries", str(session.auto_recoveries))
    stats.add_row("Typing pauses", str(session.pauses))
    stats.add_row("", "")
    stats.add_row("Device", engine.device.serial if engine.device else "—")
    stats.add_row("Interval", f"{engine.config.interval_seconds}s")
    stats.add_row("Mirror", "[green]ON[/green]" if scrcpy.is_running else "[dim]OFF[/dim]")

    # Commands bar
    stats.add_row("", "")
    if show_help:
        stats.add_row("[bold]Commands[/bold]", "")
        stats.add_row("  [cyan]n[/cyan]", "Skip to next reel")
        stats.add_row("  [cyan]l[/cyan] / [cyan]s[/cyan]", "Like / Save reel")
        stats.add_row("  [cyan]+[/cyan] / [cyan]-[/cyan]", "Volume Up / Down")
        stats.add_row("  [cyan]h[/cyan]", "Toggle this help")
        stats.add_row("  [cyan]q[/cyan]", "Stop session")
        stats.add_row("", "")
        stats.add_row("[bold]How it works[/bold]", "")
        stats.add_row("", "[dim]• Stops scrolling when you type[/dim]")
        stats.add_row("", "[dim]• Auto-skips Sponsored ads[/dim]")
        stats.add_row("", "[dim]• Blocks reels with your keywords[/dim]")
    else:
        stats.add_row("[dim]n[/dim]=next [dim]l[/dim]=like [dim]s[/dim]=save [dim]+/-[/dim]=vol [dim]h[/dim]=help [dim]q[/dim]=quit", "")

    is_paused = engine.last_status == "paused"
    border_style = "yellow" if is_paused else "green"
    return Panel(stats, title="[bold] reelax — Live [/bold]", border_style=border_style, box=box.ROUNDED)


# ──────────────────────────────────────────────
#  Interactive Menu
# ──────────────────────────────────────────────

def show_menu():
    """Show the main interactive menu."""
    console.clear()
    console.print(f"[bold green]{LOGO}[/bold green]")
    console.print(f"[dim]  Auto-scroll Reels while you code. v{__version__}[/dim]\n")

    # Device status
    try:
        devices = list_devices()
        if devices:
            console.print(f"  [green]●[/green] Device: [bold]{devices[0]}[/bold]")
        else:
            console.print(f"  [red]●[/red] No device connected")
    except ADBNotInstalledError:
        console.print(f"  [red]●[/red] ADB not installed")
        devices = []

    # scrcpy status
    if ScrcpyManager.is_installed():
        console.print(f"  [green]●[/green] Screen mirror: ready")
    else:
        console.print(f"  [yellow]●[/yellow] Screen mirror: scrcpy not found")

    console.print()

    # Menu
    menu = Table(show_header=False, box=box.SIMPLE, padding=(0, 3))
    menu.add_column(style="bold cyan", width=4)
    menu.add_column(style="bold white", width=28)
    menu.add_column(style="dim")

    menu.add_row("1", "Start  (with screen mirror)", "Phone appears on your screen")
    menu.add_row("2", "Start  (scroll only)", "No mirror window")
    menu.add_row("3", "Cadence", "Change scroll speed")
    menu.add_row("4", "WiFi Connect", "Connect to phone wirelessly")
    menu.add_row("5", "Devices", "List connected phones")
    menu.add_row("6", "Doctor", "Diagnose your setup")
    menu.add_row("7", "Customization", "Edit keywords & config")
    menu.add_row("", "", "")
    menu.add_row("h", "Help", "How reelax works")
    menu.add_row("0", "Exit", "")

    console.print(Panel(menu, title="[bold] Menu [/bold]", border_style="cyan"))
    console.print()

    return Prompt.ask("[bold cyan]→[/bold cyan]", choices=["0", "1", "2", "3", "4", "5", "6", "7", "h"], default="1")


# ──────────────────────────────────────────────
#  Session Runner (with live dashboard + inline commands)
# ──────────────────────────────────────────────

def run_session(with_mirror: bool = True, interval: float = 20.0):
    """Run a scrolling session with live dashboard and keyboard shortcuts."""
    user_config = load_config()

    scroll_config = ScrollConfig(
        interval_seconds=interval,
        idle_threshold_seconds=user_config.keyboard.idle_threshold_seconds,
        blocklist_keywords=user_config.scroll.blocklist_keywords,
    )

    engine = ScrollEngine(config=scroll_config)
    scrcpy = ScrcpyManager()
    show_help = False

    try:
        # Connect device
        device = connect_device()
        engine.device = device
        console.print(f"\n  [green]✔[/green] Device: [bold]{device.serial}[/bold]")

        # Auto-launch Instagram Reels
        if device.open_instagram_reels():
            console.print(f"  [green]✔[/green] Instagram Reels opened")
            time.sleep(2)  # Wait for Instagram to load
        else:
            console.print(f"  [yellow]⚠[/yellow] Could not open Instagram — open Reels manually")

        # Launch scrcpy (small, pinned, always on top)
        if with_mirror and ScrcpyManager.is_installed():
            if scrcpy.start(device.serial):
                console.print(f"  [green]✔[/green] Screen mirror: [bold]pinned & always-on-top[/bold]")
                time.sleep(1.5)
            else:
                console.print(f"  [yellow]⚠[/yellow] Could not start mirror")
        elif with_mirror:
            console.print(f"  [yellow]⚠[/yellow] scrcpy not installed — run [bold]winget install Genymobile.scrcpy[/bold]")

        # Start engine components
        engine.session.start()
        engine._running = True
        
        # We start the listener here so we can give feedback
        from reelax.core.keyboard import start_listener
        if start_listener():
            console.print(f"  [green]✔[/green] Keyboard monitor active")
        else:
            console.print(f"  [yellow]⚠[/yellow] Keyboard monitor failed to start")

        console.print(f"\n  [bold green]▶ Session started![/bold green]\n")

        # Live dashboard with inline command support
        with Live(build_dashboard(engine, scrcpy, show_help), console=console, refresh_per_second=2) as live:
            while engine._running:
                # Tick: check for ads, scroll or wait
                engine._tick()

                # Wait loop with command checking
                slept = 0.0
                while slept < engine.config.interval_seconds and engine._running:
                    time.sleep(0.3)
                    slept += 0.3
                    engine._time_on_current_reel += 0.3

                    # Track typing state (no tapping — just stops scrolling)
                    engine._handle_typing_state()

                    # Check for inline keyboard commands
                    key = get_pressed_key()
                    if key == "n":
                        engine.skip_to_next()
                    elif key == "l":
                        engine.device.like_reel()
                        live.update(build_dashboard(engine, scrcpy, show_help))
                    elif key == "s":
                        engine.device.save_reel()
                        live.update(build_dashboard(engine, scrcpy, show_help))
                    elif key == "+":
                        engine.device.volume_up()
                    elif key == "-":
                        engine.device.volume_down()
                    elif key == "h":
                        show_help = not show_help
                    elif key == "q":
                        engine._running = False

                    # Update live display
                    live.update(build_dashboard(engine, scrcpy, show_help))

    except KeyboardInterrupt:
        pass
    except DeviceNotFoundError as e:
        console.print(f"\n  [red]✖[/red] {e}")
        input("\n  Press Enter...")
        return
    except ADBNotInstalledError as e:
        console.print(f"\n  [red]✖[/red] {e}")
        input("\n  Press Enter...")
        return
    finally:
        engine.stop()
        scrcpy.stop()

        # Session summary
        s = engine.session
        console.print()
        summary = Table(show_header=False, box=None, padding=(0, 2))
        summary.add_column(style="bold cyan", width=20)
        summary.add_column()
        summary.add_row("Duration", s.elapsed_display)
        summary.add_row("Reels scrolled", str(s.reels_scrolled))
        summary.add_row("Ads skipped", str(s.ads_skipped))
        summary.add_row("Keywords blocked", str(s.keywords_filtered))
        summary.add_row("Auto-recoveries", str(s.auto_recoveries))
        summary.add_row("Typing pauses", str(s.pauses))
        console.print(Panel(summary, title="[bold] Session Summary [/bold]", border_style="cyan"))
        console.print()
        input("  Press Enter to go back...")


# ──────────────────────────────────────────────
#  WiFi Connect
# ──────────────────────────────────────────────

def run_wifi_connect():
    """Connect to a device over WiFi ADB."""
    console.print()
    console.print("[bold]WiFi ADB Connection[/bold]\n")
    console.print("  [dim]Step 1: Connect phone via USB first[/dim]")
    console.print("  [dim]Step 2: Run this to enable WiFi mode[/dim]")
    console.print("  [dim]Step 3: Disconnect USB, enter the IP below[/dim]\n")

    # Check if there's a USB device we can switch to TCP mode
    try:
        devices = list_devices()
        if devices:
            console.print(f"  [green]●[/green] USB device found: [bold]{devices[0]}[/bold]")
            enable = Prompt.ask("\n  Enable WiFi ADB on this device?", choices=["y", "n"], default="y")
            if enable == "y":
                result = subprocess.run(
                    ["adb", "-s", devices[0], "tcpip", "5555"],
                    capture_output=True, text=True,
                )
                console.print(f"  [green]✔[/green] WiFi mode enabled: {result.stdout.strip()}")
                console.print("  [dim]You can now disconnect the USB cable.[/dim]\n")
    except Exception:
        pass

    ip = Prompt.ask("  Enter phone IP address (e.g. [bold]192.168.1.5[/bold])")
    if not ip:
        return

    host = f"{ip}:5555" if ":" not in ip else ip

    try:
        device = connect_wifi(host)
        console.print(f"\n  [green]✔[/green] Connected via WiFi: [bold]{device.serial}[/bold]")
    except DeviceNotFoundError as e:
        console.print(f"\n  [red]✖[/red] {e}")
    except ADBNotInstalledError as e:
        console.print(f"\n  [red]✖[/red] {e}")

    console.print()
    input("  Press Enter to go back...")


# ──────────────────────────────────────────────
#  Cadence Picker
# ──────────────────────────────────────────────

def choose_cadence() -> float:
    console.print()
    console.print("[bold]Choose scroll speed:[/bold]\n")
    console.print("  [cyan]1[/cyan]  Slow   — 30s per reel  [dim](chill background)[/dim]")
    console.print("  [cyan]2[/cyan]  Medium — 20s per reel  [dim](balanced)[/dim]")
    console.print("  [cyan]3[/cyan]  Fast   — 8s per reel   [dim](rapid discovery)[/dim]")
    console.print("  [cyan]4[/cyan]  Custom — enter your own")
    console.print()

    choice = Prompt.ask("[bold cyan]→[/bold cyan]", choices=["1", "2", "3", "4"], default="2")

    if choice == "1":
        return CADENCE_INTERVALS[Cadence.SLOW]
    elif choice == "2":
        return CADENCE_INTERVALS[Cadence.MEDIUM]
    elif choice == "3":
        return CADENCE_INTERVALS[Cadence.FAST]
    else:
        return float(IntPrompt.ask("  Seconds per reel", default=15))


# ──────────────────────────────────────────────
#  Help Screen
# ──────────────────────────────────────────────

def show_help_screen():
    console.print()

    help_text = Table(show_header=False, box=None, padding=(0, 2))
    help_text.add_column(style="bold cyan", width=22)
    help_text.add_column()

    help_text.add_row("[bold]What is reelax?[/bold]", "")
    help_text.add_row("", "Auto-scrolls Instagram Reels on your phone")
    help_text.add_row("", "while you code. Pauses when you type,")
    help_text.add_row("", "resumes when you stop. Skips ads.")
    help_text.add_row("", "")
    help_text.add_row("[bold]How it works[/bold]", "")
    help_text.add_row("  ADB", "Sends swipe/tap commands to your phone")
    help_text.add_row("  Keyboard monitor", "Detects when you're typing")
    help_text.add_row("  scrcpy", "Mirrors phone screen on your PC")
    help_text.add_row("", "")
    help_text.add_row("[bold]During a session[/bold]", "")
    help_text.add_row("  [cyan]n[/cyan]", "Skip to next reel")
    help_text.add_row("  [cyan]h[/cyan]", "Toggle help overlay")
    help_text.add_row("  [cyan]q[/cyan] or [cyan]Ctrl+C[/cyan]", "Stop session")
    help_text.add_row("", "")
    help_text.add_row("[bold]Setup[/bold]", "")
    help_text.add_row("  USB", "Plug in phone with USB Debugging ON")
    help_text.add_row("  WiFi", "Use menu option 4 to connect wirelessly")
    help_text.add_row("  Config", f"Edit {CONFIG_FILE}")

    console.print(Panel(help_text, title="[bold] Help [/bold]", border_style="cyan"))
    console.print()
    input("  Press Enter to go back...")


# ──────────────────────────────────────────────
#  Doctor / Devices / Config (inline versions)
# ──────────────────────────────────────────────

def run_doctor():
    console.print("\n[bold]Diagnostics[/bold]\n")

    try:
        result = subprocess.run(["adb", "version"], capture_output=True, text=True)
        ver = result.stdout.strip().split("\n")[0]
        console.print(f"  [green]✔[/green] ADB — {ver}")
    except FileNotFoundError:
        console.print("  [red]✖[/red] ADB not found")

    try:
        found = list_devices()
        if found:
            for s in found:
                console.print(f"  [green]✔[/green] Device — {s}")
        else:
            console.print("  [red]✖[/red] No device")
    except ADBNotInstalledError:
        pass

    if ScrcpyManager.is_installed():
        console.print("  [green]✔[/green] scrcpy installed")
    else:
        console.print("  [yellow]⚠[/yellow] scrcpy missing")

    try:
        found = list_devices()
        if found:
            result = subprocess.run(
                ["adb", "-s", found[0], "shell", "pm", "list", "packages", "com.instagram.android"],
                capture_output=True, text=True,
            )
            if "com.instagram.android" in result.stdout:
                console.print("  [green]✔[/green] Instagram installed")
            else:
                console.print("  [yellow]⚠[/yellow] Instagram not found")
    except Exception:
        pass

    if CONFIG_FILE.exists():
        console.print(f"  [green]✔[/green] Config — {CONFIG_FILE}")
    else:
        console.print(f"  [yellow]⚠[/yellow] No config file")

    console.print()
    input("  Press Enter to go back...")


def run_devices():
    console.print()
    try:
        found = list_devices()
        if not found:
            console.print("  [yellow]No devices found.[/yellow]")
        else:
            table = Table(title="Devices", border_style="green")
            table.add_column("#", style="bold cyan", width=4)
            table.add_column("Serial", style="bold white")
            for i, serial in enumerate(found, 1):
                table.add_row(str(i), serial)
            console.print(table)
    except ADBNotInstalledError:
        console.print("  [red]✖[/red] ADB not installed")
    console.print()
    input("  Press Enter to go back...")


def run_customization():
    console.print("\n[bold]Customization & Settings[/bold]\n")
    
    config = load_config()
    
    while True:
        console.print(f"  [cyan]1[/cyan]  Blocklist Keywords: [bold]{', '.join(config.scroll.blocklist_keywords) if config.scroll.blocklist_keywords else 'None'}[/bold]")
        console.print("  [cyan]2[/cyan]  Reset Config to Defaults")
        console.print("  [cyan]0[/cyan]  Back")
        console.print()

        choice = Prompt.ask("[bold cyan]→[/bold cyan]", choices=["0", "1", "2"], default="0")

        if choice == "1":
            words = Prompt.ask("  Enter comma-separated keywords to block (or leave empty to clear)")
            if words.strip():
                config.scroll.blocklist_keywords = [w.strip().lower() for w in words.split(",")]
            else:
                config.scroll.blocklist_keywords = []
            save_config(config)
            console.print("  [green]✔[/green] Keywords updated\n")
        elif choice == "2":
            config = ReelaxConfig()
            save_config(config)
            console.print(f"  [green]✔[/green] Config reset to defaults\n")
        elif choice == "0":
            break


# ──────────────────────────────────────────────
#  Main Loop
# ──────────────────────────────────────────────

def main():
    """Main interactive dashboard loop."""
    current_interval = 20.0

    while True:
        try:
            choice = show_menu()

            if choice == "0":
                console.print("\n  [dim]See you later! 👋[/dim]\n")
                break
            elif choice == "1":
                run_session(with_mirror=True, interval=current_interval)
            elif choice == "2":
                run_session(with_mirror=False, interval=current_interval)
            elif choice == "3":
                current_interval = choose_cadence()
                console.print(f"\n  [green]✔[/green] Speed: [bold]{current_interval}s[/bold] per reel")
                time.sleep(1)
            elif choice == "4":
                run_wifi_connect()
            elif choice == "5":
                run_devices()
            elif choice == "6":
                run_doctor()
            elif choice == "7":
                run_customization()
            elif choice == "h":
                show_help_screen()

        except KeyboardInterrupt:
            console.print("\n\n  [dim]Goodbye! 👋[/dim]\n")
            break
        except Exception as e:
            console.print(f"\n  [red]Error: {e}[/red]")
            time.sleep(2)


if __name__ == "__main__":
    main()
