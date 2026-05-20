"""ADB interface for reelax — fast, cross-platform, WiFi-ready."""

import subprocess
from typing import List

from loguru import logger

from reelax.core.exceptions import DeviceNotFoundError, ADBNotInstalledError
from reelax.core.physics import get_screen_size as _get_phys_size, eased_swipe, _adb_swipe_fallback


class ADBDevice:
    """Represents a connected Android device. All commands use the device serial."""

    def __init__(self, serial: str):
        self.serial = serial

    def _run(self, args: List[str], timeout: float = 5) -> subprocess.CompletedProcess:
        cmd = ["adb", "-s", self.serial] + args
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise ADBNotInstalledError()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB command timed out: {' '.join(args)}")
            return subprocess.CompletedProcess(cmd, 1, "", "timeout")

    def shell(self, command: str, timeout: float = 5) -> str:
        result = self._run(["shell", command], timeout=timeout)
        return result.stdout.strip()

    def swipe(self, x: int, y_start: int, y_end: int, duration_ms: int = 300) -> None:
        self.shell(f"input swipe {x} {y_start} {x} {y_end} {duration_ms}", timeout=3)

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}", timeout=3)

    def key(self, keycode: str) -> None:
        self.shell(f"input keyevent {keycode}", timeout=3)

    def wake_screen(self) -> None:
        screen_state = self.shell("dumpsys power | grep 'Display Power' | head -1", timeout=2)
        if "OFF" in screen_state.upper():
            logger.info("Screen off — waking.")
            self.key("KEYCODE_WAKEUP")

    def open_instagram_reels(self) -> bool:
        self.wake_screen()
        result = self._run([
            "shell", "monkey", "-p", "com.instagram.android",
            "-c", "android.intent.category.LAUNCHER", "1",
        ], timeout=5)

        if result.returncode == 0:
            logger.info("Opened Instagram.")
            import time
            time.sleep(2.5)
            w, h = self.get_screen_size()
            tap_x = w // 2
            tap_y = h - int(h * 0.05)
            self.tap(tap_x, tap_y)
            logger.info(f"Tapped Reels tab at ({tap_x}, {tap_y})")
            return True

        logger.warning("Could not open Instagram.")
        return False

    def get_foreground_package(self) -> str:
        output = self.shell("dumpsys window displays", timeout=2)
        for line in output.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                if "null" not in line and "/" in line:
                    for token in line.replace("}", "").replace("{", "").split():
                        if "/" in token and "." in token:
                            return token.split("/")[0]
        return ""

    def is_instagram_foreground(self) -> bool:
        return "com.instagram.android" in self.get_foreground_package()

    def get_screen_size(self) -> tuple[int, int]:
        return _get_phys_size(self.serial)

    def natural_swipe(self) -> bool:
        u2_dev = self.get_u2()
        w, h = self.get_screen_size()
        if u2_dev:
            return eased_swipe(u2_dev, w, h)
        return _adb_swipe_fallback(self.serial, w, h)

    def get_u2(self):
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
        self.key("KEYCODE_BACK")

    def like_reel(self) -> bool:
        import time as _time
        w, h = self.get_screen_size()
        u2_dev = self.get_u2()

        if u2_dev:
            # Strategy 1: Find like button by content-desc or resource-id
            for selector in [
                u2_dev(descriptionContains="Like"),
                u2_dev(descriptionContains="like"),
                u2_dev(resourceId="com.instagram.android:id/like_button"),
                u2_dev(text="Like"),
            ]:
                try:
                    if selector.exists(timeout=0.5):
                        selector.click()
                        logger.info("Like via accessibility selector")
                        return True
                except Exception:
                    continue

            # Strategy 2: Double-tap center via uiautomator2
            try:
                u2_dev.double_click(w // 2, int(h * 0.44))
                logger.info("Like via uiautomator2 double-click")
                return True
            except Exception as e:
                logger.warning(f"uiautomator2 double-click failed: {e}")

        # Strategy 3: ADB shell double-tap at center
        cx, cy = w // 2, int(h * 0.44)
        try:
            for _ in range(2):
                self.tap(cx, cy)
                _time.sleep(0.06)
            logger.info("Like via ADB double-tap")
            return True
        except Exception:
            return False

    def save_reel(self) -> bool:
        u2_dev = self.get_u2()
        if u2_dev:
            try:
                btn = u2_dev(descriptionContains="Save")
                if btn.exists(timeout=2):
                    btn.click()
                    return True
                btn2 = u2_dev(textContains="Save")
                if btn2.exists(timeout=1):
                    btn2.click()
                    return True
            except Exception as e:
                logger.warning(f"Save by element failed: {e}")
        w, h = self.get_screen_size()
        save_x = int(w * 0.88)
        save_y = int(h * 0.83)
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


def connect_device(serial: str | None = None) -> ADBDevice:
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
