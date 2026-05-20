import time
import threading
import platform
from loguru import logger

_last_key: float = 0.0
_lock = threading.Lock()
_active = False
_use_ctypes = False
_poll_thread = None
_hotkey_thread = None
_engine_ref = None

# ─── Try keyboard library first ──────────────────────────────────────────────

try:
    import keyboard as _kb
    _KB_AVAILABLE = True
except ImportError:
    _KB_AVAILABLE = False


def _on_key(event) -> None:
    global _last_key
    with _lock:
        _last_key = time.monotonic()


# ─── Windows ctypes fallback (no admin needed) ─────────────────────────────

def _init_ctypes():
    global _use_ctypes
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        global _GetAsyncKeyState
        _GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
        _use_ctypes = True
        return True
    except Exception:
        return False


VK_CODES = list(range(0x08, 0xFF))
KEY_PRESSED = 0x8000

CTRL_VK = 0x11
SHIFT_VK = 0x10

HOTKEY_MAP = {
    "ctrl+shift+n": (CTRL_VK, SHIFT_VK, 0x4E),
    "ctrl+shift+l": (CTRL_VK, SHIFT_VK, 0x4C),
    "ctrl+shift+s": (CTRL_VK, SHIFT_VK, 0x53),
    "ctrl+shift+p": (CTRL_VK, SHIFT_VK, 0x50),
    "ctrl+shift+q": (CTRL_VK, SHIFT_VK, 0x51),
}


def _ctypes_poll_loop():
    """Poll thread: detect ANY keypress for typing detection."""
    global _last_key
    while _active:
        for vk in VK_CODES:
            if _GetAsyncKeyState(vk) & KEY_PRESSED:
                with _lock:
                    _last_key = time.monotonic()
        time.sleep(0.01)


def _ctypes_hotkey_loop():
    """Poll thread: check for hotkey combos."""
    global _engine_ref
    last_state = {hk: False for hk in HOTKEY_MAP}
    while _active:
        for hk_name, (mod1, mod2, key) in HOTKEY_MAP.items():
            pressed = (
                (_GetAsyncKeyState(mod1) & KEY_PRESSED) and
                (_GetAsyncKeyState(mod2) & KEY_PRESSED) and
                (_GetAsyncKeyState(key) & KEY_PRESSED)
            )
            if pressed and not last_state[hk_name]:
                last_state[hk_name] = True
                if _engine_ref:
                    logger.info(f"Hotkey: {hk_name}")
                    if hk_name == "ctrl+shift+n":
                        _engine_ref.skip()
                    elif hk_name == "ctrl+shift+l":
                        _engine_ref.like()
                    elif hk_name == "ctrl+shift+s":
                        _engine_ref.save()
                    elif hk_name == "ctrl+shift+p":
                        _engine_ref.toggle_pause()
                    elif hk_name == "ctrl+shift+q":
                        _engine_ref.stop()
            elif not pressed:
                last_state[hk_name] = False
        time.sleep(0.05)


# ─── Public API ──────────────────────────────────────────────────────────────

def start_listener() -> bool:
    global _active, _use_ctypes, _poll_thread

    if _active:
        return True

    # Strategy 1: Try keyboard library
    if _KB_AVAILABLE:
        try:
            _kb.on_press(_on_key, suppress=False)
            _active = True
            logger.info("Keyboard listener active (keyboard lib)")
            return True
        except Exception as e:
            logger.warning(f"keyboard lib failed: {e}")

    # Strategy 2: Windows ctypes fallback (no admin needed)
    if _init_ctypes():
        _active = True
        _poll_thread = threading.Thread(target=_ctypes_poll_loop, daemon=True)
        _poll_thread.start()
        logger.info("Keyboard listener active (ctypes polling, no admin needed)")
        return True

    logger.warning(
        "Keyboard listener failed. Typing detection disabled. "
        "On Windows, try running as Administrator."
    )
    return False


def is_typing(idle_threshold: float = 3.0) -> bool:
    with _lock:
        return (time.monotonic() - _last_key) < idle_threshold


def register_hotkeys(engine) -> None:
    global _engine_ref, _hotkey_thread

    _engine_ref = engine

    # Strategy 1: keyboard library hotkeys
    if _KB_AVAILABLE and not _use_ctypes:
        try:
            _kb.add_hotkey("ctrl+shift+n", engine.skip,         suppress=True)
            _kb.add_hotkey("ctrl+shift+l", engine.like,         suppress=True)
            _kb.add_hotkey("ctrl+shift+s", engine.save,         suppress=True)
            _kb.add_hotkey("ctrl+shift+p", engine.toggle_pause, suppress=True)
            _kb.add_hotkey("ctrl+shift+q", engine.stop,         suppress=True)
            logger.info("Global hotkeys: Ctrl+Shift+{N=next, L=like, S=save, P=pause, Q=quit}")
            return
        except Exception as e:
            logger.warning(f"keyboard hotkeys failed: {e}")

    # Strategy 2: ctypes polling hotkeys
    if _use_ctypes:
        _hotkey_thread = threading.Thread(target=_ctypes_hotkey_loop, daemon=True)
        _hotkey_thread.start()
        logger.info("Hotkey polling active (ctypes, no admin needed)")
        return

    logger.warning("Hotkey registration failed — no fallback available")


def stop_listener() -> None:
    global _active, _poll_thread, _hotkey_thread, _engine_ref

    _active = False
    _engine_ref = None

    if _KB_AVAILABLE and not _use_ctypes:
        try:
            _kb.unhook_all()
        except Exception:
            pass

    _poll_thread = None
    _hotkey_thread = None
    logger.info("Keyboard listeners stopped.")



