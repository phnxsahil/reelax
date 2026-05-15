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

    def check_for_ad_text(self) -> bool:
        """Fast check for Sponsored/ad text on screen."""
        try:
            output = self.shell(
                "dumpsys activity top | grep -iE 'Sponsored|Shop Now|Learn More|Install Now|Sign Up|Get Offer'",
                timeout=2,
            )
            return len(output.strip()) > 0
        except Exception:
            return False

    def check_for_keywords(self, keywords: List[str]) -> bool:
        """Fast check if any of the blocked keywords are on screen."""
        if not keywords:
            return False
        
        # Build a regex like 'politics|crypto|trading'
        pattern = "|".join(keywords)
        try:
            output = self.shell(
                f"dumpsys activity top | grep -iE '{pattern}'",
                timeout=2,
            )
            return len(output.strip()) > 0
        except Exception:
            return False

    def press_back(self) -> None:
        """Press the Back button."""
        self.key("KEYCODE_BACK")
        
    def volume_up(self) -> None:
        """Press Volume Up button."""
        self.key("KEYCODE_VOLUME_UP")
        
    def volume_down(self) -> None:
        """Press Volume Down button."""
        self.key("KEYCODE_VOLUME_DOWN")
        
    def like_reel(self) -> None:
        """Double tap the center of the screen to like."""
        # 540x1200 is center for most 1080x2400 screens
        self.shell("input tap 540 1200 && input tap 540 1200")
        
    def save_reel(self) -> None:
        """Tap the save button (typically bottom right corner)."""
        # 950x2000 is approximately the save button on a 1080x2400 screen
        self.tap(950, 2000)


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
