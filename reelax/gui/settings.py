import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path
from reelax.core.config import (
    ReelaxConfig, DeviceConfig, ScrollSettings, KeyboardSettings,
    DisplaySettings, MirrorConfig, BrowserConfig,
    save_config, CONFIG_PATH, write_default_config,
)
from loguru import logger


def open_settings(config: ReelaxConfig, on_save=None, parent_root=None):
    """Open the settings UI in a new thread. If parent_root is provided,
    use it as the Tk root (must be on same thread). Otherwise spawn
    a dedicated thread with its own Tk instance."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_default_config(CONFIG_PATH)

    if parent_root is not None:
        _build_dialog(parent_root, config, on_save)
    else:
        t = threading.Thread(target=_spawn_dialog, args=(config, on_save), daemon=True)
        t.start()


def _spawn_dialog(config, on_save):
    root = tk.Tk()
    root.withdraw()
    _build_dialog(root, config, on_save)
    root.mainloop()


def _build_dialog(root, config, on_save):
    win = tk.Toplevel(root)
    win.title("Reelax Settings")
    win.geometry("680x520")
    win.minsize(620, 480)
    win.resizable(True, True)

    try:
        ico = str(Path(__file__).parent.parent / "assets" / "icon.ico")
        if Path(ico).exists():
            win.iconbitmap(default=ico)
    except Exception:
        pass

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    fields = {}

    def _add_tab(text, items):
        f = ttk.Frame(notebook, padding=12)
        notebook.add(f, text=text)
        row = 0
        for label, widget_def in items:
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            w = widget_def(f)
            w.grid(row=row, column=1, sticky="ew", pady=3)
            f.columnconfigure(1, weight=1)
            key = label.lower().replace(" ", "_").replace(".", "")
            fields[key] = w
            row += 1
        f.grid_rowconfigure(row, weight=1)
        return f

    _add_tab("General", [
        ("Mode", lambda p: _mode_frame(p, config, fields)),
    ])

    _add_tab("Scroll", [
        ("Interval (sec)", lambda p: tk.Spinbox(p, from_=3.0, to=120.0, increment=0.5, textvariable=_sv(config.scroll.interval_seconds, "interval_seconds", fields))),
        ("Skip ads", lambda p: _cb(p, config.scroll.ad_skip_enabled, "ad_skip_enabled", fields)),
        ("Blocklist", lambda p: _blocklist_frame(p, config, fields)),
    ])

    _add_tab("Device", [
        ("Serial", lambda p: tk.Entry(p, textvariable=_sv(config.device.serial or "", "device_serial", fields))),
        ("Connection", lambda p: ttk.Combobox(p, values=["usb", "wifi"], textvariable=_sv(config.device.connection, "device_connection", fields), state="readonly")),
        ("WiFi host", lambda p: tk.Entry(p, textvariable=_sv(config.device.wifi_host or "", "device_wifi_host", fields))),
    ])

    _add_tab("Keyboard", [
        ("Enabled", lambda p: _cb(p, config.keyboard.enabled, "keyboard_enabled", fields)),
        ("Idle threshold (sec)", lambda p: tk.Spinbox(p, from_=1.0, to=30.0, increment=0.5, textvariable=_sv(config.keyboard.idle_threshold_seconds, "keyboard_idle_threshold", fields))),
    ])

    _add_tab("Mirror", [
        ("Width", lambda p: tk.Spinbox(p, from_=200, to=1080, increment=10, textvariable=_iv(config.mirror.width, "mirror_width", fields))),
        ("Pos X", lambda p: tk.Spinbox(p, from_=-100, to=4000, increment=1, textvariable=_iv(config.mirror.position_x, "mirror_position_x", fields))),
        ("Pos Y", lambda p: tk.Spinbox(p, from_=-100, to=4000, increment=1, textvariable=_iv(config.mirror.position_y, "mirror_position_y", fields))),
        ("Always on top", lambda p: _cb(p, config.mirror.always_on_top, "mirror_always_on_top", fields)),
        ("Borderless", lambda p: _cb(p, config.mirror.borderless, "mirror_borderless", fields)),
        ("Audio", lambda p: _cb(p, config.mirror.audio, "mirror_audio", fields)),
    ])

    _add_tab("Browser", [
        ("Width", lambda p: tk.Spinbox(p, from_=200, to=1920, increment=10, textvariable=_iv(config.browser.width, "browser_width", fields))),
        ("Height", lambda p: tk.Spinbox(p, from_=400, to=1200, increment=10, textvariable=_iv(config.browser.height, "browser_height", fields))),
        ("Headless", lambda p: _cb(p, config.browser.headless, "browser_headless", fields)),
        ("User data dir", lambda p: _dir_entry(p, config.browser.user_data_dir, fields)),
    ])

    _add_tab("Display", [
        ("Theme", lambda p: ttk.Combobox(p, values=["dark", "light"], textvariable=_sv(config.display.theme, "display_theme", fields), state="readonly")),
        ("Show stats", lambda p: _cb(p, config.display.show_stats, "display_show_stats", fields)),
    ])

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill="x", padx=8, pady=(0, 8))

    ttk.Button(btn_frame, text="Save", command=lambda: _do_save(config, fields, root, win, on_save)).pack(side="right", padx=(4, 0))
    ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="right", padx=(4, 0))
    ttk.Button(btn_frame, text="Open YAML", command=lambda: _open_yaml()).pack(side="left")

    def _on_close():
        win.destroy()
        root.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.transient(root)
    win.grab_set()
    win.focus_set()


def _sv(default, key, fields):
    v = tk.StringVar(value=str(default))
    fields[key] = v
    return v


def _iv(default, key, fields):
    v = tk.IntVar(value=int(default))
    fields[key] = v
    return v


def _bv(default, key, fields):
    v = tk.BooleanVar(value=bool(default))
    fields[key] = v
    return v


def _cb(parent, default, key, fields):
    v = _bv(default, key, fields)
    return ttk.Checkbutton(parent, variable=v)


def _mode_frame(parent, config, fields):
    f = ttk.Frame(parent)
    v = tk.StringVar(value=config.mode)
    fields["mode"] = v
    ttk.Radiobutton(f, text="ADB (Phone)", variable=v, value="adb").pack(side="left", padx=4)
    ttk.Radiobutton(f, text="Browser", variable=v, value="browser").pack(side="left", padx=4)
    return f


def _blocklist_frame(parent, config, fields):
    f = ttk.Frame(parent)
    lb = tk.Listbox(f, height=4)
    lb.pack(side="left", fill="both", expand=True)
    for kw in config.scroll.blocklist_keywords:
        lb.insert("end", kw)

    btnf = ttk.Frame(f)
    btnf.pack(side="left", padx=(4, 0))

    kw_var = tk.StringVar()
    entry = ttk.Entry(btnf, textvariable=kw_var)
    entry.pack(fill="x")

    def add_kw():
        val = kw_var.get().strip()
        if val and val not in lb.get(0, "end"):
            lb.insert("end", val)
            kw_var.set("")

    def remove_kw():
        sel = lb.curselection()
        if sel:
            lb.delete(sel[0])

    ttk.Button(btnf, text="Add", command=add_kw).pack(fill="x", pady=2)
    ttk.Button(btnf, text="Remove", command=remove_kw).pack(fill="x", pady=2)
    fields["blocklist_keywords_widget"] = lb
    return f


def _dir_entry(parent, default, fields):
    f = ttk.Frame(parent)
    v = tk.StringVar(value=default)
    fields["browser_user_data_dir"] = v
    e = ttk.Entry(f, textvariable=v)
    e.pack(side="left", fill="x", expand=True)

    def browse():
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Select browser profile directory")
        if d:
            v.set(d)

    ttk.Button(f, text="Browse\u2026", command=browse).pack(side="left", padx=(4, 0))
    return f


def _do_save(config, fields, root, win, on_save):
    try:
        config.mode = fields["mode"].get()
        config.device.serial = fields["device_serial"].get()
        config.device.connection = fields["device_connection"].get()
        config.device.wifi_host = fields["device_wifi_host"].get() or None

        config.scroll.interval_seconds = float(fields["interval_seconds"].get())
        config.scroll.ad_skip_enabled = fields["ad_skip_enabled"].get()
        kw_list = fields["blocklist_keywords_widget"]
        config.scroll.blocklist_keywords = list(kw_list.get(0, "end"))

        config.keyboard.enabled = fields["keyboard_enabled"].get()
        config.keyboard.idle_threshold_seconds = float(fields["keyboard_idle_threshold"].get())

        config.mirror.width = int(fields["mirror_width"].get())
        config.mirror.position_x = int(fields["mirror_position_x"].get())
        config.mirror.position_y = int(fields["mirror_position_y"].get())
        config.mirror.always_on_top = fields["mirror_always_on_top"].get()
        config.mirror.borderless = fields["mirror_borderless"].get()
        config.mirror.audio = fields["mirror_audio"].get()

        config.browser.width = int(fields["browser_width"].get())
        config.browser.height = int(fields["browser_height"].get())
        config.browser.headless = fields["browser_headless"].get()
        config.browser.user_data_dir = fields["browser_user_data_dir"].get()

        config.display.theme = fields["display_theme"].get()
        config.display.show_stats = fields["display_show_stats"].get()

        save_config(config)
        logger.info("Settings saved via UI")

        if on_save:
            on_save(config)

        win.destroy()
        root.destroy()
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        messagebox.showerror("Save Error", f"Failed to save settings:\n{e}", parent=win)


def _open_yaml():
    import subprocess, platform
    cfg = CONFIG_PATH
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", str(cfg)])
        elif platform.system() == "Windows":
            subprocess.run(["notepad", str(cfg)])
        else:
            subprocess.run(["xdg-open", str(cfg)])
    except Exception as e:
        logger.error(f"Failed to open config file: {e}")


def pick_device_dialog(devices: list[str], parent_root=None) -> str | None:
    """Show a dialog to pick an ADB device from a list. Returns the serial
    of the chosen device, or None if cancelled."""
    result = [None]

    if parent_root is not None:
        _do_pick(parent_root, devices, result)
    else:
        root = tk.Tk()
        root.withdraw()
        _do_pick(root, devices, result)
        root.mainloop()

    return result[0]


def _do_pick(root, devices, result):
    win = tk.Toplevel(root)
    win.title("Select ADB Device")
    win.geometry("400x220")
    win.resizable(False, False)

    try:
        ico = str(Path(__file__).parent.parent / "assets" / "icon.ico")
        if Path(ico).exists():
            win.iconbitmap(default=ico)
    except Exception:
        pass

    ttk.Label(win, text="Multiple ADB devices detected.\nSelect one to use:").pack(pady=(12, 6))

    lb = tk.Listbox(win, height=5)
    for d in devices:
        lb.insert("end", d)
    lb.pack(fill="both", expand=True, padx=16)
    if devices:
        lb.selection_set(0)

    btnf = ttk.Frame(win)
    btnf.pack(fill="x", padx=12, pady=(6, 10))

    def select():
        sel = lb.curselection()
        if sel:
            result[0] = lb.get(sel[0])
        win.destroy()
        root.destroy()

    def cancel():
        result[0] = None
        win.destroy()
        root.destroy()

    ttk.Button(btnf, text="Select", command=select).pack(side="right", padx=(4, 0))
    ttk.Button(btnf, text="Cancel", command=cancel).pack(side="right", padx=(4, 0))

    win.protocol("WM_DELETE_WINDOW", cancel)
    win.transient(root)
    win.grab_set()
    win.focus_set()
