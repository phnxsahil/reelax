import time
from dataclasses import dataclass, field
from enum import Enum


from loguru import logger
from pydantic import BaseModel

from reelax.core.adb import ADBDevice, connect_device
from reelax.core.keyboard import start_listener, stop_listener, is_typing
from reelax.core.detector import is_ad_reel, is_blocked_keyword
from reelax.core.physics import get_screen_size


class Cadence(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


CADENCE_INTERVALS = {
    Cadence.SLOW: 30.0,
    Cadence.MEDIUM: 20.0,
    Cadence.FAST: 8.0,
}


@dataclass
class ScrollSession:
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


class ScrollConfig(BaseModel):
    interval_seconds: float = 20.0
    idle_threshold_seconds: float = 3.0
    ad_skip_enabled: bool = True
    blocklist_keywords: list[str] = []


class ScrollEngine:
    def __init__(self, config=None, device_serial: str | None = None):
        self.config = config
        self.device: ADBDevice | None = None
        self._device_serial = device_serial
        self.session = ScrollSession()
        self._running = False
        self._paused = False
        self._time_on_current_reel = 0.0
        self.last_status = "idle"

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def stats(self) -> dict:
        return {
            "scrolls": self.session.reels_scrolled,
            "ads_skipped": self.session.ads_skipped,
            "pauses": self.session.pauses,
            "session_minutes": int(self.session.elapsed_seconds // 60),
        }

    def skip(self) -> None:
        if not self.device or not self._running:
            return
        self.device.natural_swipe()
        self.session.record_scroll()
        self._time_on_current_reel = 0.0
        self.last_status = "scrolling"

    def like(self) -> None:
        if not self.device:
            return
        self.device.like_reel()

    def save(self) -> None:
        if not self.device:
            return
        self.device.save_reel()

    def pause(self) -> None:
        self._paused = True
        self.last_status = "paused"

    def resume(self) -> None:
        self._paused = False
        self.last_status = "scrolling"

    def toggle_pause(self) -> None:
        if self._paused:
            self.resume()
        else:
            self.pause()

    def _get_interval(self) -> float:
        if self.config is None:
            return 20.0
        if hasattr(self.config, 'scroll'):
            return getattr(self.config.scroll, 'interval_seconds', 20.0)
        return getattr(self.config, 'interval_seconds', 20.0)

    def _get_idle_threshold(self) -> float:
        if self.config is None:
            return 3.0
        if hasattr(self.config, 'keyboard'):
            return getattr(self.config.keyboard, 'idle_threshold_seconds', 3.0)
        return getattr(self.config, 'idle_threshold_seconds', 3.0)

    def _get_ad_skip_enabled(self) -> bool:
        if self.config is None:
            return True
        if hasattr(self.config, 'scroll'):
            return getattr(self.config.scroll, 'ad_skip_enabled', True)
        return getattr(self.config, 'ad_skip_enabled', True)

    def _get_blocklist(self) -> list:
        if self.config is None:
            return []
        if hasattr(self.config, 'scroll'):
            return getattr(self.config.scroll, 'blocklist_keywords', [])
        return getattr(self.config, 'blocklist_keywords', [])

    def start(self, serial: str | None = None) -> None:
        logger.info("Initializing Scroll Engine...")
        if not self.device:
            self.device = connect_device(serial or self._device_serial)
        logger.info(f"Connected to device: {self.device.serial}")

        listener_ok = start_listener()
        if not listener_ok:
            logger.warning("Typing detection disabled — scrolling without pause support")

        self.session.start()
        self._running = True
        self._run_loop()

    def stop(self) -> None:
        self._running = False
        stop_listener()

    def _run_loop(self) -> None:
        interval = self._get_interval()
        logger.info(f"Scroll loop started (interval: {interval}s)")
        try:
            while self._running:
                self._tick()
                slept = 0.0
                while slept < interval and self._running:
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
        threshold = self._get_idle_threshold()
        if is_typing(threshold):
            self.session.record_pause()
            self.last_status = "paused"
        else:
            if self.last_status == "paused":
                self.last_status = "scrolling"
            self.session.record_resume()

    def _tick(self) -> None:
        if not self.device:
            return

        if self._paused:
            self.last_status = "paused"
            return

        threshold = self._get_idle_threshold()
        if is_typing(threshold):
            self.last_status = "paused"
            return

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

        if self._get_ad_skip_enabled() and is_ad_reel(self.device):
            self.last_status = "ad_skip"
            self.session.record_ad_skip()
            self.device.natural_swipe()
            self.session.record_scroll()
            self._time_on_current_reel = 0.0
            logger.info(f"Ad skipped (total: {self.session.ads_skipped})")
            time.sleep(1.0)
            return

        blocklist = self._get_blocklist()
        if blocklist and is_blocked_keyword(self.device, blocklist):
            self.last_status = "keyword_skip"
            self.session.record_keyword_filter()
            self.device.natural_swipe()
            self.session.record_scroll()
            self._time_on_current_reel = 0.0
            logger.info(f"Filtered reel (total: {self.session.keywords_filtered})")
            time.sleep(1.0)
            return

        if self._running and not is_typing(threshold):
            self.last_status = "scrolling"
            self.device.natural_swipe()
            self.session.record_scroll()
            self._time_on_current_reel = 0.0
            logger.info(f"Reel #{self.session.reels_scrolled} | {self.session.elapsed_display}")
