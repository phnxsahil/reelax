"""Scroll loop, cadence engine, ad handling, and session stats for reelax."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

from loguru import logger
from pydantic import BaseModel

from reelax.core.adb import ADBDevice, connect_device
from reelax.core.keyboard import KeyboardMonitor


# ──────────────────────────────────────────────
#  Cadence Modes
# ──────────────────────────────────────────────

class Cadence(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"

CADENCE_INTERVALS = {
    Cadence.SLOW: 30.0,
    Cadence.MEDIUM: 20.0,
    Cadence.FAST: 8.0,
}


# ──────────────────────────────────────────────
#  Session Stats
# ──────────────────────────────────────────────

@dataclass
class ScrollSession:
    """Tracks live session statistics."""
    started_at: float = 0.0
    reels_scrolled: int = 0
    ads_skipped: int = 0
    keywords_filtered: int = 0
    auto_recoveries: int = 0
    pauses: int = 0
    _was_paused: bool = field(default=False, repr=False)

    def start(self) -> None:
        self.started_at = time.time()

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at == 0:
            return 0.0
        return time.time() - self.started_at

    @property
    def elapsed_display(self) -> str:
        secs = int(self.elapsed_seconds)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs}h {mins}m {secs}s"
        elif mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def record_scroll(self) -> None:
        self.reels_scrolled += 1

    def record_ad_skip(self) -> None:
        self.ads_skipped += 1

    def record_keyword_filter(self) -> None:
        self.keywords_filtered += 1

    def record_recovery(self) -> None:
        self.auto_recoveries += 1

    def record_pause(self) -> None:
        if not self._was_paused:
            self.pauses += 1
            self._was_paused = True

    def record_resume(self) -> None:
        self._was_paused = False


# ──────────────────────────────────────────────
#  Scroll Config
# ──────────────────────────────────────────────

class ScrollConfig(BaseModel):
    interval_seconds: float = 20.0
    idle_threshold_seconds: float = 3.0
    swipe_x: int = 500
    swipe_start_y: int = 1600
    swipe_end_y: int = 300
    swipe_duration_ms: int = 300
    ad_skip_enabled: bool = True
    blocklist_keywords: list[str] = []


# ──────────────────────────────────────────────
#  Scroll Engine
# ──────────────────────────────────────────────

class ScrollEngine:
    """Scrolls reels, pauses on typing, skips ads, auto-recovers.

    Design:
      - NO screen tapping (avoids accidentally clicking ad buttons)
      - Uses fast `dumpsys` checks instead of slow `uiautomator dump`
      - Auto-recovers if an ad opens a browser (presses Back)
    """

    def __init__(self, config: Optional[ScrollConfig] = None):
        self.config = config or ScrollConfig()
        self.device: Optional[ADBDevice] = None
        self.kb_monitor = KeyboardMonitor(idle_threshold=self.config.idle_threshold_seconds)
        self.session = ScrollSession()
        self._running = False
        self._time_on_current_reel = 0.0
        self.last_status = "idle"

    @property
    def is_paused(self) -> bool:
        return self.kb_monitor.is_user_typing

    def start(self, serial: Optional[str] = None) -> None:
        """Start the scrolling session (blocking)."""
        logger.info("Initializing Scroll Engine...")

        if not self.device:
            self.device = connect_device(serial)
        logger.info(f"Connected to device: {self.device.serial}")

        self.kb_monitor.start()
        self.session.start()
        self._running = True
        self._run_loop()

    def stop(self) -> None:
        self._running = False
        self.kb_monitor.stop()

    def skip_to_next(self) -> None:
        """Manually skip to the next reel."""
        if not self.device:
            return
        self.device.swipe(
            x=self.config.swipe_x,
            y_start=self.config.swipe_start_y,
            y_end=self.config.swipe_end_y,
            duration_ms=self.config.swipe_duration_ms,
        )
        self.session.record_scroll()
        self._time_on_current_reel = 0.0
        self.last_status = "scrolling"

    def _run_loop(self) -> None:
        logger.info(f"Scroll loop started (interval: {self.config.interval_seconds}s)")
        try:
            while self._running:
                self._tick()
                slept = 0.0
                while slept < self.config.interval_seconds and self._running:
                    time.sleep(0.5)
                    slept += 0.5
                    self._time_on_current_reel += 0.5
                    self._handle_typing_state()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Scroll loop error: {e}")
            self.stop()
            raise

    def _handle_typing_state(self) -> None:
        """Track typing — no tapping, just pause the scroll timer."""
        if self.kb_monitor.is_user_typing:
            self.session.record_pause()
            self.last_status = "paused"
        else:
            self.session.record_resume()

    def _tick(self) -> None:
        """Single tick: check state → recover → skip ad → scroll."""
        if not self.device:
            return

        # 1. Typing → do nothing
        if self.kb_monitor.is_user_typing:
            self.last_status = "paused"
            return

        # 2. Auto-recover if we left Instagram (ad opened browser/external app)
        if not self.device.is_instagram_foreground():
            self.last_status = "recovering"
            self.session.record_recovery()
            for _ in range(3):
                self.device.press_back()
                time.sleep(0.4)
                if self.device.is_instagram_foreground():
                    break
            time.sleep(0.5)
            return

        # 3. Ad detection → skip
        if self.config.ad_skip_enabled and self.device.check_for_ad_text():
            self.last_status = "ad_skip"
            self.session.record_ad_skip()
            self.device.swipe(
                x=self.config.swipe_x,
                y_start=self.config.swipe_start_y,
                y_end=self.config.swipe_end_y,
                duration_ms=self.config.swipe_duration_ms,
            )
            self.session.record_scroll()
            self._time_on_current_reel = 0.0
            logger.info(f"⚡ Ad skipped (total: {self.session.ads_skipped})")
            return

        # 3.5 Keyword Filtering → skip
        if self.config.blocklist_keywords and self.device.check_for_keywords(self.config.blocklist_keywords):
            self.last_status = "keyword_skip"
            self.session.record_keyword_filter()
            self.device.swipe(
                x=self.config.swipe_x,
                y_start=self.config.swipe_start_y,
                y_end=self.config.swipe_end_y,
                duration_ms=self.config.swipe_duration_ms,
            )
            self.session.record_scroll()
            self._time_on_current_reel = 0.0
            logger.info(f"🛑 Filtered reel based on keyword (total: {self.session.keywords_filtered})")
            return

        # 4. Normal scroll
        self.last_status = "scrolling"
        self.device.swipe(
            x=self.config.swipe_x,
            y_start=self.config.swipe_start_y,
            y_end=self.config.swipe_end_y,
            duration_ms=self.config.swipe_duration_ms,
        )
        self.session.record_scroll()
        self._time_on_current_reel = 0.0
        logger.info(f"⏭ Reel #{self.session.reels_scrolled} | {self.session.elapsed_display}")
