import tkinter as tk
from tkinter import ttk
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from loguru import logger


@dataclass
class DashboardControls:
    get_engine: callable
    start: callable
    stop: callable
    toggle_pause: callable
    like: callable
    save: callable


BG      = "#0f0f16"
CARD_BG = "#1a1a2e"
TEXT    = "#e0e0e0"
DIM     = "#888899"
GREEN   = "#00e678"
AMBER   = "#ffb400"
RED     = "#ff4444"
BLUE    = "#4488ff"

STATUS_COLORS = {
    "scrolling": GREEN,
    "paused": AMBER,
    "idle": DIM,
    "stopped": DIM,
    "ad_skip": "#ff8800",
    "recovering": BLUE,
    "keyword_skip": "#ff44aa",
}


def open_dashboard(controls: DashboardControls):
    t = threading.Thread(target=_spawn_dashboard, args=(controls,), daemon=True)
    t.start()


def _spawn_dashboard(controls):
    try:
        root = tk.Tk()
        DashboardWindow(root, controls)
        root.mainloop()
    except Exception as e:
        logger.error(f"Dashboard window crashed: {e}")
        import traceback
        traceback.print_exc()


class DashboardWindow:
    def __init__(self, root, controls):
        self.root = root
        self.controls = controls
        self._running = True
        self._prev_stats = {"scrolls": 0, "ads_skipped": 0, "pauses": 0, "session_minutes": 0, "keywords_skipped": 0}
        self._prev_status = ""
        self._events = []
        self._scroll_buckets = [0] * 12
        self._bucket_interval = 5.0
        self._last_bucket_time = time.monotonic()

        root.title("Reelax Dashboard")
        root.geometry("680x620")
        root.minsize(620, 560)
        root.configure(bg=BG)

        try:
            ico = str(Path(__file__).parent.parent / "assets" / "icon.ico")
            if Path(ico).exists():
                root.iconbitmap(default=ico)
        except Exception:
            pass

        self._style = ttk.Style(root)
        self._style.theme_use("clam")
        for name, fg, bg in [
            ("Dash.TLabel", TEXT, BG),
            ("DashCard.TLabel", TEXT, CARD_BG),
            ("DashVal.TLabel", GREEN, CARD_BG),
            ("DashLog.TLabel", "#cccccc", BG),
        ]:
            self._style.configure(name, foreground=fg, background=bg, font=("Segoe UI", 10))

        self.win = root
        self._build_ui()
        self._update_loop()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.focus_set()

    def _make_card(self, parent, label, row, col):
        f = tk.Frame(parent, bg=CARD_BG, bd=1, relief="flat", highlightbackground="#2a2a3e", highlightthickness=1)
        f.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        parent.columnconfigure(col, weight=1)
        tk.Label(f, text=label, bg=CARD_BG, fg=DIM, font=("Segoe UI", 8, "bold")).pack(pady=(6, 0))
        val = tk.Label(f, text="0", bg=CARD_BG, fg=GREEN, font=("Segoe UI", 22, "bold"))
        val.pack(pady=(0, 6))
        return val

    def _build_ui(self):
        # Status bar
        status_frame = tk.Frame(self.win, bg=BG)
        status_frame.pack(fill="x", padx=14, pady=(12, 0))

        self._status_dot = tk.Canvas(status_frame, width=16, height=16, bg=BG, highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 6))
        self._dot_id = self._status_dot.create_oval(2, 2, 14, 14, fill=DIM, outline="")

        self._status_label = tk.Label(status_frame, text="Idle", bg=BG, fg=DIM, font=("Segoe UI", 13, "bold"))
        self._status_label.pack(side="left")

        self._mode_badge = tk.Label(status_frame, text="ADB", bg="#2a2a3e", fg=TEXT, font=("Segoe UI", 8), padx=8, pady=2)
        self._mode_badge.pack(side="right")

        # Stats cards
        cards_frame = tk.Frame(self.win, bg=BG)
        cards_frame.pack(fill="x", padx=10, pady=(8, 4))

        self._card_reels = self._make_card(cards_frame, "REELS", 0, 0)
        self._card_ads = self._make_card(cards_frame, "ADS SKIPPED", 0, 1)
        self._card_pauses = self._make_card(cards_frame, "PAUSES", 0, 2)
        self._card_time = self._make_card(cards_frame, "TIME", 0, 3)
        self._card_keywords = self._make_card(cards_frame, "KEYWORDS", 0, 4)

        # Action buttons
        btn_frame = tk.Frame(self.win, bg=BG)
        btn_frame.pack(fill="x", padx=14, pady=(4, 8))

        self._btn_start = tk.Button(btn_frame, text="\u25b6 Start", bg="#1a5a2e", fg=GREEN, activebackground="#2a7a3e", activeforeground=GREEN, bd=0, padx=14, pady=4, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._btn_start.pack(side="left", padx=2)
        self._btn_start.configure(command=self._on_start)

        self._btn_pause = tk.Button(btn_frame, text="\u23f8 Pause", bg="#5a4a00", fg=AMBER, activebackground="#7a6a10", activeforeground=AMBER, bd=0, padx=14, pady=4, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._btn_pause.pack(side="left", padx=2)
        self._btn_pause.configure(command=self._on_toggle_pause)

        self._btn_stop = tk.Button(btn_frame, text="\u23f9 Stop", bg="#5a1a1a", fg=RED, activebackground="#7a2a2a", activeforeground=RED, bd=0, padx=14, pady=4, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._btn_stop.pack(side="left", padx=2)
        self._btn_stop.configure(command=self._on_stop)

        tk.Label(btn_frame, bg=BG).pack(side="left", padx=6)

        self._btn_like = tk.Button(btn_frame, text="\u2665 Like", bg="#4a1a2a", fg="#ff6688", activebackground="#6a2a3a", activeforeground="#ff6688", bd=0, padx=14, pady=4, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._btn_like.pack(side="left", padx=2)
        self._btn_like.configure(command=self._on_like)

        self._btn_save = tk.Button(btn_frame, text="\u2b50 Save", bg="#1a2a4a", fg=BLUE, activebackground="#2a3a6a", activeforeground=BLUE, bd=0, padx=14, pady=4, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._btn_save.pack(side="left", padx=2)
        self._btn_save.configure(command=self._on_save)

        # Event log
        log_label = tk.Label(self.win, text="EVENT LOG", bg=BG, fg=DIM, font=("Segoe UI", 8, "bold"), anchor="w")
        log_label.pack(fill="x", padx=14, pady=(4, 0))

        log_frame = tk.Frame(self.win, bg=CARD_BG, bd=1, highlightbackground="#2a2a3e", highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=14, pady=(2, 4))

        self._log_text = tk.Text(log_frame, bg=CARD_BG, fg="#cccccc", font=("Consolas", 9), bd=0, highlightthickness=0, wrap="word", state="disabled")
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)

        # Activity graph
        graph_label = tk.Label(self.win, text="ACTIVITY (scrolls / 5s)", bg=BG, fg=DIM, font=("Segoe UI", 8, "bold"), anchor="w")
        graph_label.pack(fill="x", padx=14, pady=(2, 0))

        graph_frame = tk.Frame(self.win, bg=CARD_BG, bd=1, highlightbackground="#2a2a3e", highlightthickness=1, height=80)
        graph_frame.pack(fill="x", padx=14, pady=(2, 12))
        graph_frame.pack_propagate(False)

        self._graph_canvas = tk.Canvas(graph_frame, bg=CARD_BG, highlightthickness=0, height=80)
        self._graph_canvas.pack(fill="both", expand=True)

    def _log(self, message, color="#cccccc"):
        self._log_text.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        tag = f"tag_{len(self._events)}"
        self._log_text.insert("end", f"{ts}  ", ("dim",))
        self._log_text.insert("end", f"{message}\n", (tag,))
        self._log_text.tag_configure("dim", foreground=DIM, font=("Consolas", 8))
        self._log_text.tag_configure(tag, foreground=color, font=("Consolas", 9))
        self._log_text.see("end")
        self._log_text.configure(state="disabled")
        self._events.append((ts, message))
        if len(self._events) > 200:
            self._events.pop(0)

    def _draw_graph(self):
        c = self._graph_canvas
        c.delete("all")
        w = c.winfo_width() or 600
        h = c.winfo_height() or 80
        if w < 20:
            return
        max_val = max(self._scroll_buckets) if self._scroll_buckets else 1
        if max_val == 0:
            max_val = 1
        bar_w = max(6, (w - 20) // len(self._scroll_buckets))
        for i, val in enumerate(self._scroll_buckets):
            x0 = 10 + i * bar_w
            x1 = x0 + bar_w - 2
            bar_h = max(2, (val / max_val) * (h - 16))
            y0 = h - 8 - bar_h
            y1 = h - 8
            color = GREEN if val > 0 else "#2a2a3e"
            c.create_rectangle(x0, y0, x1, y1, fill=color, outline="", width=0)

    def _update_loop(self):
        if not self._running:
            return
        try:
            self._refresh()
        except Exception:
            pass
        self.root.after(1000, self._update_loop)

    def _refresh(self):
        engine = self.controls.get_engine()
        if engine:
            status = getattr(engine, "last_status", "") or "idle"
            stats = engine.stats if hasattr(engine, "stats") else {}
            mode = "Browser" if "Browser" in type(engine).__name__ else "ADB"
            self._mode_badge.configure(text=mode)

            dot_color = STATUS_COLORS.get(status, DIM)
            self._status_dot.itemconfig(self._dot_id, fill=dot_color)
            label = status.replace("_", " ").title()
            self._status_label.configure(text=label, fg=dot_color)

            self._card_reels.configure(text=str(stats.get("scrolls", 0)))
            self._card_ads.configure(text=str(stats.get("ads_skipped", 0)))
            self._card_pauses.configure(text=str(stats.get("pauses", 0)))
            self._card_keywords.configure(text=str(stats.get("keywords_skipped", 0)))
            mins = stats.get("session_minutes", 0)
            secs = int(stats.get("session_minutes", 0) * 60) % 60
            self._card_time.configure(text=f"{mins}m")

            if stats.get("scrolls", 0) > self._prev_stats.get("scrolls", 0):
                self._log(f"Scrolled reel #{stats['scrolls']}", GREEN)
            if stats.get("ads_skipped", 0) > self._prev_stats.get("ads_skipped", 0):
                self._log("Ad skipped", "#ff8800")
            if stats.get("keywords_skipped", 0) > self._prev_stats.get("keywords_skipped", 0):
                self._log("Keyword filtered", "#ff44aa")
            if stats.get("pauses", 0) > self._prev_stats.get("pauses", 0):
                self._log("Paused (typing detected)", AMBER)
            self._prev_stats = stats

            now = time.monotonic()
            if now - self._last_bucket_time >= self._bucket_interval:
                self._scroll_buckets.pop(0)
                self._scroll_buckets.append(stats.get("scrolls", 0) - self._prev_stats.get("scrolls", 0))
                self._last_bucket_time = now
                self._draw_graph()
        else:
            self._status_dot.itemconfig(self._dot_id, fill=DIM)
            self._status_label.configure(text="Idle", fg=DIM)
            self._mode_badge.configure(text="--")
            for card in [self._card_reels, self._card_ads, self._card_pauses, self._card_keywords, self._card_time]:
                card.configure(text="0")

    def _on_start(self):
        self.controls.start()

    def _on_stop(self):
        self.controls.stop()
        self._log("Session stopped", RED)

    def _on_toggle_pause(self):
        self.controls.toggle_pause()

    def _on_like(self):
        self.controls.like()
        self._log("Liked reel", "#ff6688")

    def _on_save(self):
        self.controls.save()
        self._log("Saved reel", BLUE)

    def _on_close(self):
        self._running = False
        self.win.destroy()
