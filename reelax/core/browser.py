from __future__ import annotations

import json
import time
from pathlib import Path

from loguru import logger


CONFIG_DIR = Path.home() / ".reelax"
PROFILE_DIR = CONFIG_DIR / "browser_profile"
COOKIE_FILE = CONFIG_DIR / "cookies.json"
REELS_URL  = "https://www.instagram.com/reels/"


class BrowserSession:

    def __init__(self, config=None, device_serial: str | None = None):
        self.config = config
        self.window_w      = self._cfg_val('browser', 'width', 360)
        self.window_h      = self._cfg_val('browser', 'height', 760)
        self.interval       = self._cfg_val('scroll', 'interval_seconds', 20.0)
        self.idle_threshold = self._cfg_val('keyboard', 'idle_threshold_seconds', 3.0)
        self.skip_ads       = self._cfg_val('scroll', 'ad_skip_enabled', True)
        self.blocklist      = self._cfg_val('scroll', 'blocklist_keywords', [])

        self._pw      = None
        self._context = None
        self._page    = None
        self._running   = False
        self._paused    = False
        self._reel_ready = False
        self.last_status = "idle"
        self._launch_error: str | None = None

        self._stats_data = {
            "scrolls": 0, "ads_skipped": 0,
            "keywords_skipped": 0, "pauses": 0,
            "session_start": None,
        }

    def _cfg_val(self, section, key, default):
        if self.config is None:
            return default
        sec = getattr(self.config, section, None)
        if sec is None:
            return default
        return getattr(sec, key, default)

    @staticmethod
    def check_available() -> str | None:
        try:
            import playwright
        except ImportError:
            return "Playwright not installed.\nRun: pip install 'reelax[browser]'"
        try:
            import playwright.sync_api
        except ImportError:
            return "Playwright sync API not available.\nRun: pip install 'reelax[browser]'"
        return None

    # ── Common interface ─────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def stats(self) -> dict:
        session_min = 0
        start = self._stats_data.get("session_start")
        if start:
            session_min = int((time.monotonic() - start) // 60)
        return {
            "scrolls": self._stats_data["scrolls"],
            "ads_skipped": self._stats_data["ads_skipped"],
            "keywords_skipped": self._stats_data["keywords_skipped"],
            "pauses": self._stats_data["pauses"],
            "session_minutes": session_min,
        }

    def skip(self) -> None:
        try:
            self._next_reel()
        except Exception:
            pass

    def like(self) -> None:
        try:
            btn = self._page.locator('[aria-label*="Like"]').first
            if btn.is_visible(timeout=800):
                btn.click()
            else:
                vp = self._page.viewport_size
                self._page.mouse.dblclick(vp["width"] // 2, int(vp["height"] * 0.44))
        except Exception as e:
            logger.warning(f"Like failed: {e}")

    def save(self) -> None:
        try:
            btn = self._page.locator('[aria-label*="Save"]').first
            if btn.is_visible(timeout=800):
                btn.click()
        except Exception as e:
            logger.warning(f"Save failed: {e}")

    def pause(self) -> None:
        self._paused = True
        self.last_status = "paused"
        self._pause_video()

    def resume(self) -> None:
        self._paused = False
        self.last_status = "scrolling"
        self._play_video()

    def toggle_pause(self) -> None:
        if self._paused:
            self.resume()
        else:
            self.pause()

    def _pause_video(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.evaluate("document.querySelectorAll('video').forEach(v => v.pause())")
        except Exception:
            pass

    def _play_video(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.evaluate("document.querySelectorAll('video').forEach(v => v.play())")
        except Exception:
            pass

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def launch(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed.\nRun: pip install 'reelax[browser]' && playwright install chromium")
            return False

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            self._pw = sync_playwright().start()

            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir = str(PROFILE_DIR),
                headless=False,
                viewport={"width": 412, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Mobile Safari/537.36"
                ),
                args=[
                    f"--app={REELS_URL}",
                    f"--window-size={self.window_w},{self.window_h}",
                    f"--window-position=0,0",
                    "--disable-infobars",
                    "--no-default-browser-check",
                    "--disable-notifications",
                    "--disable-save-password-bubble",
                    "--disable-translate",
                    "--disable-features=TranslateUI",
                ],
                ignore_default_args=["--enable-automation"],
            )

            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()

            if REELS_URL not in self._page.url:
                self._page.goto(REELS_URL, wait_until="commit", timeout=30000)
            self._reel_ready = False

            self._lockdown_page()

            if self._needs_login():
                logger.warning("Not logged in to Instagram.\nLog in, then reelax will start.")
                self._wait_for_login(timeout=120)
                self._save_cookies()

            self._page.goto(REELS_URL, wait_until="domcontentloaded", timeout=30000)
            self._inject_favicon()
            self._inject_overlay()
            self._dismiss_popups()

            time.sleep(2)
            self._wait_for_reel()

            self._stats_data["session_start"] = time.monotonic()
            logger.info("Browser launched — app mode fullscreen")
            return True

        except Exception as e:
            msg = f"Failed to launch: {e}"
            logger.error(msg)
            self._launch_error = msg
            self._cleanup()
            return False

    def start(self, serial: str | None = None) -> None:
        self._launch_error = None
        if not self._page:
            if not self.launch():
                return
        self._running = True
        self._scroll_loop()

    def stop(self) -> None:
        self._running = False
        self._cleanup()

    # ── Scroll loop ──────────────────────────────────────────────────────────

    def _scroll_loop(self) -> None:
        from reelax.core.keyboard import is_typing

        was_typing = False
        first_scroll = True

        while self._running:
            try:
                if not self._page or self._page.is_closed():
                    logger.info("Browser window closed — stopping")
                    self._running = False
                    break

                typing = is_typing(self.idle_threshold)
                if typing:
                    if not was_typing:
                        was_typing = True
                        self._stats_data["pauses"] += 1
                        self.last_status = "paused"
                        self._update_overlay_status("paused")
                        self._pause_video()
                    time.sleep(0.15)
                    continue

                if was_typing:
                    was_typing = False
                    self.last_status = "scrolling"
                    self._update_overlay_status("scrolling")
                    if not self._paused:
                        self._play_video()

                if self._paused:
                    time.sleep(0.5)
                    continue

                if first_scroll:
                    time.sleep(3.0)
                    first_scroll = False

                if not self._reel_ready:
                    self._wait_for_reel()

                if self.skip_ads and self._is_ad():
                    logger.info("Ad — skipping")
                    self._next_reel()
                    self._stats_data["ads_skipped"] += 1
                    time.sleep(1.5)
                    continue

                if self.blocklist and self._has_blocked_keyword():
                    logger.info("Blocked keyword — skipping")
                    self._next_reel()
                    self._stats_data["keywords_skipped"] += 1
                    time.sleep(1.5)
                    continue

                for _ in range(max(1, int(self.interval / 0.5))):
                    if not self._running or not self._page or self._page.is_closed():
                        break
                    time.sleep(0.5)

                if self._running and not is_typing(self.idle_threshold) and not self._paused:
                    if self._page and not self._page.is_closed():
                        self._next_reel()

            except Exception as e:
                if self._running:
                    logger.warning(f"Scroll loop error: {e}")
                time.sleep(2)

    def _wait_for_reel(self) -> None:
        try:
            self._page.wait_for_selector('[role="presentation"] article, video, [aria-label*="reel"]',
                                          timeout=8000)
            self._reel_ready = True
        except Exception:
            try:
                self._page.wait_for_selector('article, video', timeout=5000)
                self._reel_ready = True
            except Exception:
                self._reel_ready = True

    def _next_reel(self) -> None:
        try:
            self._page.keyboard.press("ArrowDown")
            self._stats_data["scrolls"] += 1
            self.last_status = "scrolling"
            logger.debug(f"Reel {self._stats_data['scrolls']}")
            self._reel_ready = False
        except Exception as e:
            logger.warning(f"Next reel failed: {e}")

    # ── Detection ────────────────────────────────────────────────────────────

    def _is_ad(self) -> bool:
        try:
            for sel in [
                'text="Sponsored"',
                'text="Paid partnership"',
                '[aria-label*="Sponsored"]',
            ]:
                if self._page.locator(sel).count() > 0:
                    return True
        except Exception:
            pass
        return False

    def _has_blocked_keyword(self) -> bool:
        try:
            text = self._page.locator('[role="main"]').inner_text(timeout=800)
            text_lower = text.lower()
            return any(kw.lower() in text_lower for kw in self.blocklist)
        except Exception:
            return False

    # ── Kiosk lockdown (click shield + keyboard lock) ───────────────────────

    def _lockdown_page(self) -> None:
        try:
            self._page.add_init_script("""
                document.addEventListener('keydown', (e) => {
                    if (e.ctrlKey || e.metaKey) {
                        if (['t','w','n','T','W','N','r','R','j','J'].includes(e.key)) {
                            e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
                        }
                    }
                    if (e.key === 'F12' || e.key === 'Escape') {
                        e.preventDefault(); e.stopPropagation();
                    }
                }, true);

                document.addEventListener('contextmenu', (e) => e.preventDefault(), true);

                new MutationObserver(() => {
                    document.title = "reelax";
                }).observe(document.head || document.documentElement, {
                    childList: true, subtree: true, characterData: true
                });
            """)
        except Exception:
            pass

    def _inject_favicon(self) -> None:
        try:
            ico_path = str(Path(__file__).parent.parent / "assets" / "icon.ico")
            ico_url = ico_path.replace("\\", "/")
            self._page.add_init_script(f"""
                (() => {{
                    const setRx = () => {{
                        document.title = 'reelax';
                        const links = document.querySelectorAll('link[rel*="icon"], link[rel*="shortcut"]');
                        links.forEach(l => l.remove());
                        const lnk = document.createElement('link');
                        lnk.rel = 'icon'; lnk.type = 'image/x-icon';
                        lnk.href = 'file:///{ico_url}';
                        document.head?.appendChild(lnk);
                    }};
                    setRx();
                    new MutationObserver(setRx).observe(document.head, {{ childList: true, subtree: true }});
                }})();
            """)
            logger.debug("Favicon + title injected")
        except Exception as e:
            logger.warning(f"Favicon injection failed: {e}")

    # ── Custom control overlay + click shield ──────────────────────────────

    def _inject_overlay(self) -> None:
        try:
            self._page.expose_function("_reelaxLike", self.like)
            self._page.expose_function("_reelaxSave", self.save)
            self._page.expose_function("_reelaxSkip", self.skip)
        except Exception:
            pass

        try:
            self._page.add_style_tag(content="""
                #reelax-controls {
                    position: fixed; bottom: 0; left: 0; right: 0;
                    height: 64px; background: rgba(0,0,0,0.85);
                    display: flex; align-items: center;
                    justify-content: space-evenly;
                    z-index: 999999;
                    backdrop-filter: blur(12px);
                    -webkit-backdrop-filter: blur(12px);
                    border-top: 1px solid rgba(255,255,255,0.08);
                }
                #reelax-controls button {
                    background: none; border: none; color: #fff;
                    font-size: 22px; cursor: pointer;
                    width: 48px; height: 48px;
                    border-radius: 50%;
                    display: flex; align-items: center;
                    justify-content: center;
                    transition: background 0.15s;
                }
                #reelax-controls button:hover {
                    background: rgba(255,255,255,0.1);
                }
                #reelax-controls .rl-like { color: #ff3040; }
                #reelax-controls .rl-save { color: #0095f6; }
                .rl-dot-green { background: #00e678; }
                .rl-dot-amber { background: #ffb400; }
                body { padding-bottom: 72px !important; }
            """)

            self._page.evaluate("""
                // Prevent navigation from accidental clicks
                document.addEventListener('click', (e) => {
                    const path = e.composedPath();
                    for (const node of path) {
                        if (node.tagName === 'A' || node.role === 'link') {
                            e.preventDefault();
                            e.stopPropagation();
                            return;
                        }
                    }
                }, true);

                const bar = document.createElement('div');
                bar.id = 'reelax-controls';
                bar.innerHTML = `
                    <button class="rl-like" onclick="_reelaxLike()" title="Like">❤️</button>
                    <button onclick="document.querySelector('[aria-label*=\\'Comment\\']')?.click()" title="Comment">💬</button>
                    <button onclick="document.querySelector('[aria-label*=\\'Share\\']')?.click()" title="Share">📤</button>
                    <button class="rl-save" onclick="_reelaxSave()" title="Save">🔖</button>
                    <button onclick="_reelaxSkip()" title="Next">⏭️</button>
                `;
                document.body.appendChild(bar);

                document.title = 'reelax';
            """)
            logger.debug("Controls + click-blocker injected")
        except Exception as e:
            logger.warning(f"Overlay injection failed: {e}")

    def _update_overlay_status(self, status: str):
        color = "rl-dot-green" if status == "scrolling" else "rl-dot-amber" if status == "paused" else "rl-dot-green"
        try:
            self._page.evaluate(f"""
                const dot = document.querySelector('#reelax-status-dot .dot');
                if (dot) {{
                    dot.className = 'dot {color}';
                }}
            """)
        except Exception:
            pass

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _save_cookies(self) -> None:
        try:
            cookies = self._context.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(cookies, f)
            logger.debug("Cookies saved")
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")

    def _load_cookies(self) -> bool:
        if not COOKIE_FILE.exists():
            return False
        try:
            with open(COOKIE_FILE) as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
            logger.debug("Cookies loaded")
            return True
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
            return False

    def _needs_login(self) -> bool:
        try:
            return self._page.locator('input[name="username"]').count() > 0
        except Exception:
            return False

    def _wait_for_login(self, timeout: int = 120) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if not self._needs_login():
                logger.info("Login detected — proceeding")
                time.sleep(2)
                return True
            time.sleep(1)
        logger.warning("Login timeout")
        return False

    def _dismiss_popups(self) -> None:
        try:
            for text in ["Not Now", "Not now", "Cancel", "Decline", "Save Info"]:
                btn = self._page.locator(f'text="{text}"').first
                if btn.is_visible(timeout=500):
                    btn.click()
                    time.sleep(0.3)
        except Exception:
            pass

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        try:
            self._save_cookies()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._page    = None
        self._context = None
        self._pw      = None
        self.last_status = "stopped"
