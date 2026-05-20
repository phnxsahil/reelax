import subprocess
import random
import time
from loguru import logger


def get_screen_size(device_serial: str) -> tuple[int, int]:
    try:
        result = subprocess.run(
            ["adb", "-s", device_serial, "shell", "wm", "size"],
            capture_output=True, text=True, timeout=5
        )
        line = result.stdout.strip()
        if "Physical size:" in line:
            dims = line.split("Physical size:")[-1].strip()
            w, h = map(int, dims.split("x"))
            return w, h
    except Exception as e:
        logger.warning(f"Could not get screen size: {e}")
    return 1080, 2400


def eased_swipe(device, screen_width: int, screen_height: int) -> bool:
    cx = screen_width // 2 + random.randint(-25, 25)
    start_y = int(screen_height * 0.73)
    end_y = int(screen_height * 0.20)
    end_x = cx + random.randint(-15, 15)
    duration = random.uniform(0.26, 0.32)

    try:
        device.swipe(cx, start_y, end_x, end_y, duration=duration)
        return True
    except Exception as e:
        logger.warning(f"UIAutomator2 swipe failed: {e}, falling back to ADB")
        return _adb_swipe_fallback(device.serial, screen_width, screen_height)


def _adb_swipe_fallback(serial: str, w: int, h: int) -> bool:
    cx = w // 2 + random.randint(-20, 20)
    sy = int(h * 0.73)
    ey = int(h * 0.20)
    duration_ms = random.randint(260, 320)
    result = subprocess.run(
        ["adb", "-s", serial, "shell", "input", "swipe",
         str(cx), str(sy), str(cx), str(ey), str(duration_ms)],
        capture_output=True, timeout=5
    )
    return result.returncode == 0


def double_tap_like(device, screen_width: int, screen_height: int) -> bool:
    cx = screen_width // 2
    cy = int(screen_height * 0.44)
    try:
        device.double_click(cx, cy)
        return True
    except Exception:
        try:
            device.click(cx, cy)
            time.sleep(0.08)
            device.click(cx, cy)
            return True
        except Exception:
            return False
