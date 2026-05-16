"""Cross-platform keyboard monitor for reelax.

Uses the `keyboard` library. No accessibility permissions needed on macOS, 
but requires root/admin on Linux/Windows if not hooked at the driver level.
"""

import time
import threading
from typing import Optional

from loguru import logger

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

_last_key_time: float = 0.0
_lock = threading.Lock()
_hooked: bool = False


def _on_any_key(event) -> None:
    """Callback for key press events."""
    global _last_key_time
    with _lock:
        _last_key_time = time.monotonic()


def start_listener() -> bool:
    """Start the global keyboard listener."""
    global _hooked

    if not KEYBOARD_AVAILABLE:
        logger.warning(
            "keyboard library not installed. Typing detection disabled.\n"
            "Install it: pip install keyboard"
        )
        return False

    if _hooked:
        return True

    try:
        keyboard.on_press(_on_any_key, suppress=False)
        _hooked = True
        logger.info("Keyboard listener ready.")
        return True
    except Exception as e:
        logger.error(
            f"Keyboard listener failed: {e}\n"
            "macOS: Requires sudo to hook keys.\n"
            "Windows: Try running as Administrator.\n"
            "Typing detection will be disabled for this session."
        )
        return False


def is_typing(idle_threshold: float = 3.0) -> bool:
    """Returns True if user typed within the last `idle_threshold` seconds."""
    with _lock:
        if _last_key_time == 0.0:
            return False
        return (time.monotonic() - _last_key_time) < idle_threshold


def stop_listener() -> None:
    """Stop the keyboard listener if running."""
    global _hooked
    if _hooked:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        _hooked = False
        logger.info("Keyboard listener stopped.")


def register_hotkeys(engine) -> None:
    """Global hotkeys — work from any app, no terminal focus needed."""
    if not KEYBOARD_AVAILABLE:
        return

    try:
        keyboard.add_hotkey("ctrl+shift+n", lambda: engine.skip_to_next())
        keyboard.add_hotkey("ctrl+shift+l", lambda: getattr(engine.device, "like_reel", lambda: None)())
        keyboard.add_hotkey("ctrl+shift+s", lambda: getattr(engine.device, "save_reel", lambda: None)())
        # engine.toggle_pause() is not implemented yet, we can add it later if needed, or omit it.
        # keyboard.add_hotkey("ctrl+shift+p", lambda: engine.toggle_pause())
        keyboard.add_hotkey("ctrl+shift+q", lambda: engine.stop())
        logger.info("Global hotkeys registered: Ctrl+Shift+{N,L,S,Q}")
    except Exception as e:
        logger.warning(f"Failed to register global hotkeys: {e}")
