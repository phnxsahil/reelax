"""scrcpy window management for reelax."""

import subprocess
import platform
from loguru import logger
from typing import Optional


def launch_scrcpy(
    device_serial: str,
    width: int = 540,
    position_x: int = 0,
    position_y: int = 0,
    audio: bool = False,
    always_on_top: bool = True,
    borderless: bool = True,
) -> Optional[subprocess.Popen]:
    """
    Launch scrcpy as a pinned sidebar.
    Default: 420px wide, top-left corner, borderless, always on top.
    """
    cmd = ["scrcpy"]

    # Device
    cmd += ["-s", device_serial]

    # Sizing — max-size scales proportionally to phone's aspect ratio
    cmd += ["--max-size", str(width)]

    # Window chrome
    if always_on_top:
        cmd.append("--always-on-top")
    if borderless:
        cmd.append("--window-borderless")

    # Position
    cmd += ["--window-x", str(position_x)]
    cmd += ["--window-y", str(position_y)]

    # Window title
    cmd += ["--window-title", "reelax"]

    # Audio
    if not audio:
        cmd.append("--no-audio")

    # Keep phone awake while mirroring
    cmd.append("--stay-awake")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"scrcpy launched (PID {proc.pid}, width={width})")
        return proc
    except FileNotFoundError:
        logger.error(
            "scrcpy not found.\n"
            "Mac: brew install scrcpy\n"
            "Windows: winget install Genymobile.scrcpy"
        )
        return None
