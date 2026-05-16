"""Cross-platform keyboard monitor for reelax.

Uses the `pynput` library to avoid requiring Administrator privileges on Windows.
Requires Accessibility permissions on macOS.
"""

import time
import threading
from loguru import logger
from typing import Optional

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

_last_key_time: float = 0.0
_lock = threading.Lock()
_listener: Optional[keyboard.Listener] = None
_hotkeys: Optional[keyboard.GlobalHotKeys] = None

def _on_press(key) -> None:
    """Callback for any key press."""
    global _last_key_time
    with _lock:
        _last_key_time = time.monotonic()


def start_listener() -> bool:
    """Start the global keyboard listener."""
    global _listener

    if not PYNPUT_AVAILABLE:
        logger.warning("pynput not installed. Typing detection disabled.")
        return False

    if _listener and _listener.running:
        return True

    try:
        _listener = keyboard.Listener(on_press=_on_press)
        _listener.start()
        
        # macOS permission check (fails silently if no access)
        time.sleep(0.2)
        if not _listener.running:
            logger.warning("Keyboard listener died. macOS: Grant Accessibility permissions to your terminal.")
            return False
            
        logger.info("Keyboard listener ready.")
        return True
    except Exception as e:
        logger.error(f"Keyboard listener failed: {e}")
        return False


def is_typing(idle_threshold: float = 3.0) -> bool:
    """Returns True if user typed within the last `idle_threshold` seconds."""
    with _lock:
        if _last_key_time == 0.0:
            return False
        return (time.monotonic() - _last_key_time) < idle_threshold


def stop_listener() -> None:
    """Stop the keyboard listener and hotkeys."""
    global _listener, _hotkeys
    
    if _listener:
        _listener.stop()
        _listener = None
        
    if _hotkeys:
        _hotkeys.stop()
        _hotkeys = None
        
    logger.info("Keyboard listeners stopped.")


def register_hotkeys(engine) -> None:
    """Register global hotkeys via pynput."""
    global _hotkeys
    
    if not PYNPUT_AVAILABLE:
        return
        
    if _hotkeys and _hotkeys.running:
        return

    try:
        def on_next():
            logger.info("Hotkey: Next Reel")
            engine.skip_to_next()
            
        def on_like():
            logger.info("Hotkey: Like Reel")
            getattr(engine.device, "like_reel", lambda: None)()
            
        def on_save():
            logger.info("Hotkey: Save Reel")
            getattr(engine.device, "save_reel", lambda: None)()
            
        def on_stop():
            logger.info("Hotkey: Stop")
            engine.stop()

        hotkeys_mapping = {
            '<ctrl>+<shift>+n': on_next,
            '<ctrl>+<shift>+l': on_like,
            '<ctrl>+<shift>+s': on_save,
            '<ctrl>+<shift>+q': on_stop
        }

        _hotkeys = keyboard.GlobalHotKeys(hotkeys_mapping)
        _hotkeys.start()
        
        time.sleep(0.2)
        if not _hotkeys.running:
            logger.warning("Failed to start GlobalHotKeys (likely macOS permissions).")
        else:
            logger.info("Global hotkeys registered: Ctrl+Shift+{N,L,S,Q}")
            
    except Exception as e:
        logger.warning(f"Failed to register global hotkeys: {e}")
