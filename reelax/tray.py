"""System tray application for reelax."""

import threading
import sys
import os
import subprocess
import pystray
from PIL import Image, ImageDraw
from loguru import logger

from reelax.core.scroller import ScrollEngine
from reelax.core.config import load_config
from reelax.core.mirror import launch_scrcpy

engine: ScrollEngine | None = None
config = load_config()
scrcpy_proc: subprocess.Popen | None = None

def make_icon(state: str = "stopped") -> Image.Image:
    """Draw a simple circle icon for the tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    if state == "running":
        # Green circle
        d.ellipse([8, 8, 56, 56], fill="#00cc77")
        d.ellipse([22, 22, 42, 42], fill=(0, 0, 0, 0))
    else:
        # Gray circle
        d.ellipse([8, 8, 56, 56], fill="#888888")
        d.ellipse([22, 22, 42, 42], fill=(0, 0, 0, 0))
        
    return img

def update_icon_state(icon, state: str):
    icon.icon = make_icon(state)
    if state == "running":
        icon.title = "reelax — scrolling"
    else:
        icon.title = "reelax — stopped"

def start_session(icon, item):
    global engine, scrcpy_proc
    if engine and engine._running:
        return
        
    engine = ScrollEngine(config)
    
    # Launch scrcpy if configured
    if scrcpy_proc is None or scrcpy_proc.poll() is not None:
        # Connect first to get device serial
        from reelax.core.adb import connect_device
        try:
            device = connect_device()
            scrcpy_proc = launch_scrcpy(
                device_serial=device.serial,
                width=config.mirror.width,
                position_x=config.mirror.position_x,
                position_y=config.mirror.position_y,
                audio=config.mirror.audio,
                always_on_top=config.mirror.always_on_top,
                borderless=config.mirror.borderless
            )
            # Make sure reels are open
            device.open_instagram_reels()
        except Exception as e:
            logger.error(f"Failed to setup device/mirror: {e}")
            
    threading.Thread(target=engine.start, daemon=True).start()
    
    # Register global hotkeys
    from reelax.core.keyboard import register_hotkeys
    register_hotkeys(engine)
    
    update_icon_state(icon, "running")

def stop_session(icon, item):
    global engine, scrcpy_proc
    if engine:
        engine.stop()
    if scrcpy_proc:
        scrcpy_proc.terminate()
        scrcpy_proc = None
        
    # Unhook hotkeys
    from reelax.core.keyboard import stop_listener
    stop_listener()
    
    update_icon_state(icon, "stopped")

def open_settings(icon, item):
    from reelax.core.config import CONFIG_FILE
    config_path = str(CONFIG_FILE)
    if sys.platform == "darwin":
        subprocess.run(["open", config_path])
    elif sys.platform == "win32":
        # On windows we use os.startfile to open default editor
        os.startfile(config_path)
    else:
        subprocess.run(["xdg-open", config_path])

def show_hotkeys(icon, item):
    msg = (
        "Ctrl+Shift+N : Next Reel\n"
        "Ctrl+Shift+L : Like\n"
        "Ctrl+Shift+S : Save\n"
        "Ctrl+Shift+Q : Stop"
    )
    icon.notify(msg, title="Reelax Hotkeys")

def quit_app(icon, item):
    stop_session(icon, item)
    icon.stop()

def run_tray():
    icon = pystray.Icon(
        name="reelax",
        icon=make_icon("stopped"),
        title="reelax — stopped",
        menu=pystray.Menu(
            pystray.MenuItem("▶  Start scrolling", start_session, default=True),
            pystray.MenuItem("⏹  Stop", stop_session),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⌨  Show Hotkeys", show_hotkeys),
            pystray.MenuItem("⚙  Settings", open_settings),
            pystray.MenuItem("✕  Quit", quit_app),
        )
    )
    
    # Setup logger to file since there's no terminal
    from reelax.core.config import CONFIG_DIR
    log_file = CONFIG_DIR / "reelax.log"
    logger.add(log_file, rotation="1 MB", retention="3 days", level="INFO")
    
    logger.info("Reelax tray app started.")
    icon.run()

if __name__ == "__main__":
    run_tray()
