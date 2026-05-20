import platform
import threading
from pathlib import Path
from loguru import logger

import pystray
from PIL import Image, ImageDraw

from reelax.core.engine import create_engine
from reelax.core.keyboard import start_listener, register_hotkeys, stop_listener
from reelax.core.mirror import launch_scrcpy, stop_scrcpy
from reelax.core.config import load_config, save_config


_engine = None
_scrcpy_proc = None
_config = None
_tray_icon = None


def _draw_rx(d, cx, cy, sc, accent, dim):
    """Draw the reelax Rx logo at scale sc centered at cx,cy."""
    lw = max(2, int(sc * 6.5))
    sx  = cx - 14 * sc
    top = cy - 34 * sc
    bot = cy + 32 * sc
    d.line([(sx, top), (sx, bot)], fill=accent, width=lw)

    bowl_cx = cx
    bowl_cy = cy - 14 * sc
    bowl_r  = 16 * sc
    d.line([(sx, bowl_cy - bowl_r), (bowl_cx, bowl_cy - bowl_r)], fill=accent, width=lw)
    mid_y = bowl_cy + bowl_r
    d.line([(sx, mid_y), (bowl_cx, mid_y)], fill=accent, width=lw)
    d.arc(
        [bowl_cx - bowl_r, bowl_cy - bowl_r, bowl_cx + bowl_r, bowl_cy + bowl_r],
        start=270, end=90, fill=accent, width=lw,
    )

    hr = bowl_r * 0.36
    d.ellipse(
        [bowl_cx - hr, bowl_cy - hr, bowl_cx + hr, bowl_cy + hr],
        outline=dim, width=max(1, int(sc * 2)),
    )

    d.line([(bowl_cx, mid_y), (cx + 16 * sc, bot)], fill=accent, width=lw)

    x1 = cx + 10 * sc; x2 = cx + 32 * sc
    yt = cy - 2 * sc;  yb = cy + 32 * sc
    d.line([(x1, yt), (x2, yb)], fill=accent, width=lw)
    d.line([(x2, yt), (x1, yb)], fill=accent, width=lw)


def _make_icon(size: int = 64, state: str = "idle") -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sc  = size / 100.0
    corner = max(6, int(size * 0.22))

    if state == "scrolling":
        bg = (0, 50, 25, 255)
        accent = (0, 230, 120, 255)
        dim = (0, 150, 80, 160)
    elif state == "paused":
        bg = (50, 35, 0, 255)
        accent = (255, 180, 0, 255)
        dim = (180, 120, 0, 160)
    else:
        bg = (15, 15, 22, 255)
        accent = (100, 100, 120, 255)
        dim = (70, 70, 85, 160)

    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner, fill=bg)
    _draw_rx(d, size // 2, size // 2, sc, accent, dim)
    return img


def _get_icon(state: str = "idle") -> Image.Image:
    return _make_icon(64, state)


def _mode_label():
    if not _config:
        return "adb"
    return _config.mode


def _mode_display():
    m = _mode_label()
    return "📱 Phone" if m == "adb" else "🌐 Browser"


def _title_text(suffix="ready"):
    return f"reelax — {suffix} ({_mode_display()})"


def _switch_mode(icon, item, mode: str):
    global _config
    if _engine and _engine.running:
        icon.notify("Stop the session first before switching modes.", title="reelax")
        return
    _config.mode = mode
    save_config(_config)
    icon.title = _title_text("ready")
    icon.icon = _get_icon("idle")
    _rebuild_menu(icon)


def _rebuild_menu(icon):
    icon.menu = _build_menu()


def _build_menu():
    mode = _mode_label()
    return pystray.Menu(
        pystray.MenuItem("▶ Start", _start, default=True),
        pystray.MenuItem("⏸ Pause", _toggle_pause),
        pystray.MenuItem("⏹ Stop", _stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Mode", pystray.Menu(
            pystray.MenuItem(
                "📱 Phone",
                lambda icon, item: _switch_mode(icon, item, "adb"),
                checked=lambda item: mode == "adb",
                radio=True,
            ),
            pystray.MenuItem(
                "🌐 Browser",
                lambda icon, item: _switch_mode(icon, item, "browser"),
                checked=lambda item: mode == "browser",
                radio=True,
            ),
        )),
        pystray.MenuItem("📊 Stats", _show_stats),
        pystray.MenuItem("📈 Dashboard", _open_dashboard),
        pystray.MenuItem("⚙ Settings", _edit_config),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✕ Quit", _quit),
    )


def _start(icon, item):
    global _engine, _scrcpy_proc, _config
    if _engine and _engine.running:
        return

    try:
        _engine = create_engine(_config)

        if _config.mode == "adb":
            device_serial = getattr(_config.device, 'serial', None)
            if not device_serial or device_serial == "auto":
                from reelax.core.adb import list_devices
                found = list_devices()
                if not found:
                    icon.notify("No phone found. Connect via USB.", title="reelax")
                    return
                if len(found) > 1:
                    from reelax.gui.settings import pick_device_dialog
                    picked = pick_device_dialog(found)
                    if picked is None:
                        icon.notify("Device selection cancelled.", title="reelax")
                        return
                    device_serial = picked
                    _config.device.serial = picked
                    save_config(_config)
                else:
                    device_serial = found[0]

            mirror_cfg = getattr(_config, 'mirror', None)
            if mirror_cfg:
                _scrcpy_proc = launch_scrcpy(
                    device_serial,
                    width=getattr(mirror_cfg, 'width', 420),
                    position_x=getattr(mirror_cfg, 'position_x', 0),
                    position_y=getattr(mirror_cfg, 'position_y', 0),
                    audio=getattr(mirror_cfg, 'audio', False),
                )

            register_hotkeys(_engine)
            logger.info("Session started (ADB mode)")

        else:
            from reelax.core.browser import BrowserSession
            err = BrowserSession.check_available()
            if err:
                icon.notify(err + "\n\nThen: playwright install chromium", title="reelax")
                _engine = None
                return

            logger.info("Session started (browser mode)")

        def _run_and_monitor():
            try:
                _engine.start()
            finally:
                _on_engine_stop(icon)

        t = threading.Thread(target=_run_and_monitor, daemon=True)
        t.start()
        icon.icon = _get_icon("scrolling")
        icon.title = _title_text("scrolling")

    except Exception as e:
        logger.error(f"Start failed: {e}")
        icon.notify(str(e), title="reelax")


def _on_engine_stop(icon):
    global _engine, _scrcpy_proc
    _engine = None
    stop_scrcpy(_scrcpy_proc)
    _scrcpy_proc = None
    try:
        icon.icon = _get_icon("idle")
        icon.title = _title_text("stopped")
    except Exception:
        pass


def _stop(icon, item):
    global _engine
    if _engine:
        _engine.stop()
        _engine = None


def _toggle_pause(icon, item):
    global _engine
    if not _engine:
        return
    if _engine.paused:
        _engine.resume()
        icon.icon = _get_icon("scrolling")
        icon.title = _title_text("scrolling")
    else:
        _engine.pause()
        icon.icon = _get_icon("paused")
        icon.title = _title_text("paused")


def _edit_config(icon, item):
    """Open settings UI dialog."""
    from reelax.gui.settings import open_settings
    open_settings(_config, on_save=_on_settings_saved)


def _on_settings_saved(config):
    global _config
    _config = config
    if _tray_icon:
        _tray_icon.title = _title_text("ready")
        _rebuild_menu(_tray_icon)


def _show_stats(icon, item):
    if not _engine:
        icon.notify("No active session.\nStart scrolling first.", title="reelax")
        return
    s = _engine.stats
    icon.notify(
        f"Reels: {s['scrolls']}\n"
        f"Ads skipped: {s['ads_skipped']}\n"
        f"Pauses: {s['pauses']}\n"
        f"Time: {s['session_minutes']}m",
        title="reelax — session stats"
    )


def _open_dashboard(icon, item):
    try:
        from reelax.gui.dashboard import open_dashboard, DashboardControls
        ctrl = DashboardControls(
            get_engine=lambda: _engine,
            start=lambda: _start(icon, item),
            stop=lambda: _stop(icon, item),
            toggle_pause=lambda: _toggle_pause(icon, item),
            like=lambda: _engine.like() if _engine else None,
            save=lambda: _engine.save() if _engine else None,
        )
        open_dashboard(ctrl)
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        icon.notify(str(e), title="reelax")


def _quit(icon, item):
    _stop(icon, item)
    stop_listener()
    icon.stop()


def run_tray():
    global _config, _tray_icon

    if platform.system() == "Windows":
        import ctypes
        try:
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

    _config = load_config()
    start_listener()

    _tray_icon = pystray.Icon(
        name="reelax",
        icon=_get_icon("idle"),
        title=_title_text("ready"),
        menu=_build_menu(),
    )

    _tray_icon.run()
