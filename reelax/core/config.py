"""Configuration loader and validator for reelax."""

import os
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field


# --- Config Schema ---

class DeviceConfig(BaseModel):
    """Device connection settings."""
    serial: str = "auto"
    connection: str = "usb"  # "usb" | "wifi"
    wifi_host: Optional[str] = None


class ScrollSettings(BaseModel):
    """Scroll behavior settings."""
    interval_seconds: float = Field(default=20.0, ge=3.0, le=120.0)
    ad_skip_enabled: bool = True
    blocklist_keywords: list[str] = Field(default_factory=lambda: ["politics", "crypto", "trading"])


class MirrorConfig(BaseModel):
    """scrcpy window mirror settings."""
    width: int = Field(default=420, ge=200, le=1080)
    position_x: int = 0
    position_y: int = 0
    always_on_top: bool = True
    borderless: bool = True
    audio: bool = False



class KeyboardSettings(BaseModel):
    """Keyboard monitoring settings."""
    enabled: bool = True
    idle_threshold_seconds: float = Field(default=3.0, ge=1.0, le=30.0)


class DisplaySettings(BaseModel):
    """Terminal display settings."""
    theme: str = "dark"
    show_stats: bool = True


class ReelaxConfig(BaseModel):
    """Root configuration model for reelax."""
    device: DeviceConfig = DeviceConfig()
    scroll: ScrollSettings = ScrollSettings()
    keyboard: KeyboardSettings = KeyboardSettings()
    display: DisplaySettings = DisplaySettings()
    mirror: MirrorConfig = MirrorConfig()


# --- Config File Paths ---

CONFIG_DIR = Path.home() / ".reelax"
CONFIG_FILE = CONFIG_DIR / "config.yml"


# --- Loader / Saver ---

def _ensure_config_dir() -> None:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> ReelaxConfig:
    """Load config from ~/.reelax/config.yml, or return defaults."""
    if not CONFIG_FILE.exists():
        logger.info("No config file found. Using defaults.")
        return ReelaxConfig()

    try:
        with open(CONFIG_FILE, "r") as f:
            raw = yaml.safe_load(f) or {}
        config = ReelaxConfig(**raw)
        logger.info(f"Config loaded from {CONFIG_FILE}")
        return config
    except Exception as e:
        logger.warning(f"Failed to parse config file: {e}. Using defaults.")
        return ReelaxConfig()


def save_config(config: ReelaxConfig) -> None:
    """Save the current config to ~/.reelax/config.yml."""
    _ensure_config_dir()
    data = config.model_dump()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Config saved to {CONFIG_FILE}")


def get_default_config_yaml() -> str:
    """Return the default config as a YAML string (for display)."""
    config = ReelaxConfig()
    return yaml.dump(config.model_dump(), default_flow_style=False, sort_keys=False)
