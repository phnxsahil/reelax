import time
from threading import Lock
from pynput import keyboard
from loguru import logger

class KeyboardMonitor:
    """Monitors keyboard activity to detect if the user is typing."""
    
    def __init__(self, idle_threshold: float = 3.0):
        self.idle_threshold = idle_threshold
        self.last_keystroke_time = 0.0
        self._lock = Lock()
        self._listener = None

    def _on_press(self, key):
        """Callback for key press events."""
        with self._lock:
            self.last_keystroke_time = time.time()

    def start(self) -> None:
        """Start the keyboard listener in a background thread."""
        if self._listener is not None:
            return
        
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()
        logger.info("Keyboard monitor started.")

    def stop(self) -> None:
        """Stop the keyboard listener."""
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Keyboard monitor stopped.")

    @property
    def is_user_typing(self) -> bool:
        """Check if the user has typed within the idle threshold."""
        with self._lock:
            return (time.time() - self.last_keystroke_time) < self.idle_threshold

    @property
    def idle_time(self) -> float:
        """Return the time in seconds since the last keystroke."""
        with self._lock:
            return time.time() - self.last_keystroke_time
