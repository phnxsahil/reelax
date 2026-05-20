import subprocess
import platform
import shutil
import time
from loguru import logger


def launch_scrcpy(
    device_serial: str,
    width: int = 420,
    position_x: int = 0,
    position_y: int = 0,
    audio: bool = False,
) -> subprocess.Popen | None:
    if not shutil.which("scrcpy"):
        logger.error(
            "scrcpy not found.\n"
            "Mac: brew install scrcpy\n"
            "Windows: winget install Genymobile.scrcpy"
        )
        return None

    cmd = [
        "scrcpy",
        "-s", device_serial,
        "--max-size", str(width),
        "--max-fps", "30",
        "--video-codec", "h264",
        "--video-buffer", "0",
        "--always-on-top",
        "--window-borderless",
        "--window-title", "reelax",
        "--window-x", str(position_x),
        "--window-y", str(position_y),
        "--stay-awake",
        "--turn-screen-off",
        "--no-power-on",
    ]

    if not audio:
        cmd.append("--no-audio")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            logger.error("scrcpy exited immediately — check device connection")
            return None
        logger.info(f"scrcpy launched (PID {proc.pid}, {width}px wide)")
        return proc
    except Exception as e:
        logger.error(f"Failed to launch scrcpy: {e}")
        return None


def stop_scrcpy(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
