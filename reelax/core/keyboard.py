"""Cross-platform keyboard monitor for reelax.

Module-level API — no class instantiation needed.
Handles macOS Accessibility permissions gracefully.
"""

import time
import threading
from typing import Optional

from loguru import logger

try:
    from pynput import keyboard as pynput_kb
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

_last_key_time: float = 0.0
_lock = threading.Lock()
_listener: Optional[object] = None


def _on_press(key) -> None:
    """Callback for key press events."""
    global _last_key_time
    with _lock:
        _last_key_time = time.monotonic()


def start_listener() -> bool:
    """Start the global keyboard listener.

    Returns True if successfully started. On failure (missing permissions,
    missing pynput), returns False and logs guidance — scrolling continues
    without typing detection.
    """
    global _listener

    if not PYNPUT_AVAILABLE:
        logger.warning(
            "pynput not installed. Typing detection disabled.\n"
            "Install it: pip install pynput"
        )
        return False

    try:
        _listener = pynput_kb.Listener(on_press=_on_press, suppress=False)
        _listener.daemon = True
        _listener.start()

        # Verify it actually started (catches macOS Accessibility permission issues)
        time.sleep(0.2)
        if not _listener.is_alive():
            raise RuntimeError("Listener died immediately — check Accessibility permissions")

        logger.info("Keyboard listener started ✓")
        return True

    except Exception as e:
        logger.error(
            f"Keyboard listener failed: {e}\n"
            "macOS: Grant Accessibility permission to Terminal/iTerm in "
            "System Settings → Privacy & Security → Accessibility.\n"
            "Windows: Try running as Administrator.\n"
            "Typing detection will be disabled for this session."
        )
        return False


def is_typing(idle_threshold: float = 3.0) -> bool:
    """Returns True if user typed within the last `idle_threshold` seconds.

    Uses monotonic clock to avoid drift from system time changes.
    """
    with _lock:
        if _last_key_time == 0.0:
            return False
        return (time.monotonic() - _last_key_time) < idle_threshold


def stop_listener() -> None:
    """Stop the keyboard listener if running."""
    global _listener
    if _listener is not None:
        try:
            if hasattr(_listener, 'is_alive') and _listener.is_alive():
                _listener.stop()
        except Exception:
            pass
        _listener = None
        logger.info("Keyboard listener stopped.")
