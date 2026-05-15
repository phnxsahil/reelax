<div align="center">

# reelax
**Ambient flow-state. Auto-scroll Instagram Reels while you code.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OS](https://img.shields.io/badge/OS-Windows%20|%20Mac%20|%20Linux-lightgrey.svg)]()

<br/>
<img src="https://raw.githubusercontent.com/phnxsahil/reelax/main/assets/demo.gif" width="600" alt="reelax demo" />
<br/><br/>

*Reelax turns your phone into an ambient background display. It auto-scrolls Reels, pauses instantly when you type on your computer, skips sponsored ads, and filters out keywords you don't want to see.*

</div>

---

## ✨ Features

- **🧠 Smart Typing Detection**: `reelax` monitors your keyboard (locally). When you start typing, the reel pauses instantly. When you stop, it resumes.
- **⚡ Superfast Ad Skipping**: Automatically detects "Sponsored" tags and instantly skips to the next reel in ~100ms.
- **🚫 AI Keyword Filtering**: Block reels containing words like "politics" or "crypto" — `reelax` reads the screen text and skips them automatically.
- **📺 Picture-in-Picture Mirroring**: Mirrors your phone directly to your computer screen using `scrcpy` (pinned, always-on-top, small window), while turning your actual phone screen off to save battery.
- **🎮 Built-in Hotkeys**: Press `+` / `-` to change volume, `l` to double-tap like, `s` to save, or `n` to manually skip.

## 🚀 Installation

### Prerequisites
- **Android Phone** with [USB Debugging Enabled](https://developer.android.com/studio/debug/dev-options)
- **Python 3.10+**

### Windows Quick Install
Just run the included batch script. It will automatically install Python, ADB, and scrcpy using `winget` if you don't have them.
```cmd
git clone https://github.com/phnxsahil/reelax.git
cd reelax
install.bat
```

### Mac/Linux Quick Install
```bash
git clone https://github.com/phnxsahil/reelax.git
cd reelax
chmod +x install.sh
./install.sh
```

## 🎮 Usage

Plug in your Android phone via USB (or connect via WiFi ADB), open your terminal, and simply type:

```bash
reelax
```

This will launch the **Interactive Dashboard**:

```text
                  _            
  _ __ ___  ___ | | __ ___  __
 | '__/ _ \/ _ \| |/ _` \ \/ /
 | | |  __/  __/| | (_| |>  < 
 |_|  \___|\___|_|\__,_/_/\_\

  ● Device: RZCT41L9X2P
  ● Screen mirror: ready

┌──────────────────────────────────  Menu  ───────────────────────────────────┐
│                                                                             │
│     1          Start  (with screen mirror)                                  │
│     2          Start  (scroll only)                                         │
│     3          Cadence                     (Change scroll speed)            │
│     4          WiFi Connect                (Connect to phone wirelessly)    │
│     7          Customization               (Edit keywords & config)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

Press `1` to start. Your phone screen will pop up as a small pinned window, Instagram Reels will open automatically, and ambient scrolling will begin.

### Session Hotkeys
While a session is running, you can use these keys directly in the terminal:
- `n` : Skip to next reel
- `l` : Like the current reel (double tap)
- `s` : Save the current reel
- `+` / `-` : Turn phone volume up or down
- `q` : Stop the session gracefully

## ⚙️ Customization & Keywords

From the main menu, press `7` to enter the **Customization** section. Here you can add comma-separated keywords to your blocklist (e.g., `politics, trading, crypto`). 

`reelax` will scan the screen text using Android's native view hierarchy dump and instantly skip any reels matching your blocked words.

## 🛠️ Architecture
Built entirely in Python.
- `adb shell` for blazing-fast, low-level screen interaction.
- `pynput` for cross-platform global keyboard monitoring.
- `rich` for the beautiful Terminal User Interface (TUI).
- `scrcpy` for high-performance screen mirroring.

## 🤝 Contributing
Pull requests are welcome! If you'd like to add iOS support, advanced AI image filtering, or new gestures, please open an issue first to discuss what you would like to change.

## 📄 License
[MIT](https://choosealicense.com/licenses/mit/)
