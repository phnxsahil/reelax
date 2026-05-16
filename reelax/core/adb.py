"""ADB interface for reelax — fast, cross-platform, WiFi-ready."""

import subprocess
import platform
from typing import List, Optional

from loguru import logger

from reelax.core.exceptions import DeviceNotFoundError, ADBNotInstalledError


# ──────────────────────────────────────────────
#  ADB Device
# ──────────────────────────────────────────────

class ADBDevice:
    """Represents a connected Android device. All commands use the device serial."""

    def __init__(self, serial: str):
        self.serial = serial

    def _run(self, args: List[str], timeout: float = 5) -> subprocess.CompletedProcess:
        """Run an ADB command against this device. Raises on ADB missing."""
        cmd = ["adb", "-s", self.serial] + args
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise ADBNotInstalledError()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB command timed out: {' '.join(args)}")
            return subprocess.CompletedProcess(cmd, 1, "", "timeout")

    def shell(self, command: str, timeout: float = 5) -> str:
        """Run a shell command on the device and return stdout. Fast path."""
        result = self._run(["shell", command], timeout=timeout)
        return result.stdout.strip()

    def swipe(self, x: int, y_start: int, y_end: int, duration_ms: int = 300) -> None:
        """Send a swipe gesture."""
        self.shell(f"input swipe {x} {y_start} {x} {y_end} {duration_ms}", timeout=3)

    def tap(self, x: int, y: int) -> None:
        """Send a tap gesture."""
        self.shell(f"input tap {x} {y}", timeout=3)

    def key(self, keycode: str) -> None:
        """Send a key event (e.g. KEYCODE_BACK)."""
        self.shell(f"input keyevent {keycode}", timeout=3)

    def wake_screen(self) -> None:
        """Wake the screen if it's off."""
        screen_state = self.shell("dumpsys power | grep 'Display Power' | head -1", timeout=2)
        if "OFF" in screen_state.upper():
            logger.info("Screen off — waking.")
            self.key("KEYCODE_WAKEUP")

    def open_instagram_reels(self) -> bool:
        """Launch Instagram safely without clearing state.

        Note: Direct deep-linking to Reels is blocked by newer Instagram versions,
        so this safely brings Instagram to the foreground using the monkey launcher
        which preserves your current state/tabs.
        """
        self.wake_screen()

        # Safely bring Instagram to the foreground
        result = self._run([
            "shell", "monkey", "-p", "com.instagram.android",
            "-c", "android.intent.category.LAUNCHER", "1",
        ], timeout=5)
        
        if result.returncode == 0:
            logger.info("Opened Instagram.")
            
            import time
            time.sleep(2.5)  # Wait for UI to load
            
            # Read screen size to find center-bottom (where Reels tab lives)
            size_out = self.shell("wm size", timeout=2)
            if "Physical size:" in size_out:
                try:
                    # Format is "Physical size: 1080x2400"
                    dims = size_out.split(":")[1].strip().split("x")
                    width = int(dims[0])
                    height = int(dims[1])
                    
                    # Tap center X, and near bottom Y (accounting for navigation bar)
                    tap_x = width // 2
                    tap_y = height - int(height * 0.05)  # Bottom 5% of screen
                    
                    self.tap(tap_x, tap_y)
                    logger.info(f"Tapped Reels tab at ({tap_x}, {tap_y})")
                except Exception as e:
                    logger.warning(f"Failed to calculate tap coordinates: {e}")
            
            return True

        logger.warning("Could not open Instagram.")
        return False

    def get_foreground_package(self) -> str:
        """Get the current foreground app package name. ~50ms."""
        output = self.shell("dumpsys window displays", timeout=2)
        for line in output.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                if "null" not in line and "/" in line:
                    for token in line.replace("}", "").replace("{", "").split():
                        if "/" in token and "." in token:
                            return token.split("/")[0]
        return ""

    def is_instagram_foreground(self) -> bool:
        """Check if Instagram is the current foreground app."""
        return "com.instagram.android" in self.get_foreground_package()

    def get_screen_size(self) -> tuple[int, int]:
        """Get actual screen dimensions from ADB — never assume."""
        try:
            result = self._run(["shell", "wm", "size"], timeout=5)
            line = result.stdout.strip()
            # "Physical size: 1080x2400"
            if "Physical size:" in line:
                dims = line.split("Physical size:")[-1].strip()
                w, h = dims.split("x")
                return int(w), int(h)
        except Exception as e:
            logger.warning(f"Failed to get screen size: {e}")
        return 1080, 2400  # Safe default

    def natural_swipe(self) -> bool:
        """
        Perform a natural-feeling upward swipe to advance to next reel.
        Randomizes start/end coords and uses acceleration curve.
        """
        width, height = self.get_screen_size()
        
        # Vary start point slightly — looks human, avoids pattern detection
        import random
        center_x = (width // 2) + random.randint(-30, 30)
        start_y = int(height * 0.72) + random.randint(-40, 40)
        end_y = int(height * 0.22) + random.randint(-40, 40)
        duration_ms = random.randint(250, 380)  # Human swipe range

        cmd = [
            "adb", "-s", self.serial,
            "shell", "input", "swipe",
            str(center_x), str(start_y),
            str(center_x), str(end_y),
            str(duration_ms)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("Natural swipe timed out")
            return False

    def get_u2(self):
        """Lazily initialize UIAutomator2 connection."""
        if not hasattr(self, "_u2_device"):
            try:
                import uiautomator2 as u2
                self._u2_device = u2.connect(self.serial)
            except ImportError:
                logger.warning("uiautomator2 not installed. Some features may use fallbacks.")
                self._u2_device = None
            except Exception as e:
                logger.warning(f"Failed to initialize uiautomator2: {e}")
                self._u2_device = None
        return self._u2_device

    def press_back(self) -> None:
        """Press the Back button."""
        self.key("KEYCODE_BACK")
        
    def volume_up(self) -> None:
        """Press Volume Up button."""
        self.key("KEYCODE_VOLUME_UP")
        
    def volume_down(self) -> None:
        """Press Volume Down button."""
        self.key("KEYCODE_VOLUME_DOWN")
        
    def like_reel(self) -> bool:
        """Double tap the center of the screen to like."""
        width, height = self.get_screen_size()
        cx = width // 2
        cy = int(height * 0.45)
        
        u2_dev = self.get_u2()
        if u2_dev:
            try:
                u2_dev.double_click(cx, cy)
                return True
            except Exception as e:
                logger.warning(f"Like via UIAutomator2 failed: {e}")
                
        # Fallback to adb shell
        try:
            self.shell(f"input tap {cx} {cy} && input tap {cx} {cy}")
            return True
        except Exception:
            return False
        
    def save_reel(self) -> bool:
        """Tap the save button (typically bottom right corner)."""
        u2_dev = self.get_u2()
        if u2_dev:
            try:
                # Try resource ID first (most stable)
                btn = u2_dev(descriptionContains="Save")
                if btn.exists(timeout=2):
                    btn.click()
                    return True
                # Fallback: try text
                btn2 = u2_dev(textContains="Save")
                if btn2.exists(timeout=1):
                    btn2.click()
                    return True
            except Exception as e:
                logger.warning(f"Save by element failed: {e}")
                
        # Fallback to coordinate tap
        width, height = self.get_screen_size()
        # Roughly 88% width, 83% height
        save_x = int(width * 0.88)
        save_y = int(height * 0.83)
        self.tap(save_x, save_y)
        return True


# ──────────────────────────────────────────────
#  Device Discovery
# ──────────────────────────────────────────────

def list_devices() -> List[str]:
    """List serial numbers of connected ADB devices."""
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        raise ADBNotInstalledError()

    devices = []
    for line in result.stdout.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def connect_device(serial: Optional[str] = None) -> ADBDevice:
    """Connect to a specific device or auto-detect the first one."""
    devices = list_devices()

    if serial:
        if serial not in devices:
            raise DeviceNotFoundError(f"Device '{serial}' not found. Available: {devices}")
        return ADBDevice(serial)

    if not devices:
        raise DeviceNotFoundError(
            "No Android device found.\n"
            "  1. Enable USB Debugging in Developer Options\n"
            "  2. Connect your phone via USB\n"
            "  3. Accept the 'Allow USB Debugging?' prompt on your phone"
        )

    selected = devices[0]
    logger.info(f"Auto-selected device: {selected}")
    return ADBDevice(selected)


def connect_wifi(host: str) -> ADBDevice:
    """Connect to a device over WiFi ADB.

    Args:
        host: IP:port string (e.g. '192.168.1.5:5555')
    """
    if ":" not in host:
        host = f"{host}:5555"

    try:
        result = subprocess.run(
            ["adb", "connect", host],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        raise ADBNotInstalledError()

    output = result.stdout.strip()
    if "connected" in output.lower():
        logger.info(f"Connected via WiFi: {host}")
        return ADBDevice(host)

    raise DeviceNotFoundError(f"Could not connect to {host}: {output}")
