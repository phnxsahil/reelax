# Reelax

> Auto-scroll Instagram Reels while you work. Pauses automatically when you type. Resumes when you stop.

[![Version](https://img.shields.io/badge/version-0.4.0-cyan.svg)](https://github.com/phnxsahil/reelax)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)]()

**Reelax** is an ambient desktop companion for Instagram Reels. It sits quietly as a slim window on the edge of your screen, playing content at its own pace. 

**The magic**: The moment you start typing in *any* window (your IDE, terminal, or browser), the video pauses. Stop typing, and after a short idle threshold, the scrolling resumes. No reaching for your phone. No doom-scrolling spirals. Just ambient content that disappears when you're in flow.

---

## 🌟 Features

* **Smart Typing Detection**: Globally detects keyboard activity to pause/resume video playback and auto-scrolling automatically.
* **Dual Modes**: 
  * **🌐 Browser Mode**: A self-contained, clean Chromium kiosk window (no address bar). Requires no phone.
  * **📱 Phone Mode (ADB)**: Native Android mirroring via `scrcpy` + `adb`. Uses UIAutomator2 for precise tapping.
* **System Tray & Dashboard**: Full GUI dashboard for stats (reels watched, ads skipped, pauses) and a comprehensive Settings UI. No JSON editing required.
* **Ad & Keyword Skipping**: Automatically skips sponsored posts and reels containing specific blocklist keywords.
* **Global Hotkeys**: Use `Ctrl+Shift+N` to skip, `Ctrl+Shift+L` to like, `Ctrl+Shift+S` to save, entirely hands-free.

---

## 🚀 Installation

Ensure you have **Python 3.10+** installed.

```bash
git clone https://github.com/phnxsahil/reelax.git
cd reelax
pip install -e .
```

If you plan to use **Browser Mode** (recommended), install the Playwright dependencies:
```bash
pip install "reelax[browser]"
playwright install chromium
```

---

## 💻 Setup & OS Compatibility

Reelax is fully cross-platform, but handles permissions differently per OS:

### 🪟 Windows
* **Keyboard Detection**: Uses low-level `ctypes` polling. **No Administrator privileges required!**
* **Dependencies**: Works out of the box.

### 🍏 macOS
* **Keyboard Detection**: Requires the `keyboard` Python library to hook keystrokes. **You must grant Accessibility permissions** to your Terminal application (or the IDE running Reelax) via `System Settings > Privacy & Security > Accessibility`.
* **Dependencies (Phone Mode)**: If using phone mode, install ADB and Scrcpy via Homebrew:
  ```bash
  brew install android-platform-tools scrcpy
  ```

---

## 🛠️ Usage

Run the app from your terminal (or use the desktop shortcut):

```bash
reelax
```

A `℞` (Rx) icon will appear in your system tray/menu bar. 

1. Right-click the tray icon and select **Settings** to configure your preferred mode (Browser or ADB), set interval times, and add blocklist keywords.
2. Click **Start** to launch the Reels window.
3. Open the **Dashboard** from the tray to view live scrolling statistics.

---

## 📱 Phone Mode (ADB) Setup

If you prefer using your actual Android phone instead of the built-in browser:

1. Enable **Developer Options** on your Android device.
2. Enable **USB Debugging**.
3. Connect your phone via USB and tap "Allow" on the prompt.
4. Reelax will automatically launch `scrcpy` to mirror your screen and send swipe commands.

---

## ⌨️ Global Hotkeys

Control Reelax from any application without changing focus:

| Hotkey | Action |
|---|---|
| `Ctrl+Shift+N` | Skip / Next Reel |
| `Ctrl+Shift+L` | Like current reel |
| `Ctrl+Shift+S` | Save current reel |
| `Ctrl+Shift+P` | Play / Pause toggle |
| `Ctrl+Shift+Q` | Stop and exit |

---

## 🔧 Architecture

* **Browser Mode**: Powered by Playwright in `--app` mode for a chromeless experience. Video elements are controlled directly via injected Javascript.
* **Phone Mode**: ADB sends UIAutomator2 gestures for natural, human-like swipes. Screen mirroring is offloaded to `scrcpy`.
* **Typing Detection**: A lightweight background thread monitors global keypresses (via `ctypes` on Windows, or `keyboard` on macOS) to seamlessly toggle video states without interrupting your active workflow.

---

## 📄 License

MIT © [phnxsahil](https://github.com/phnxsahil)