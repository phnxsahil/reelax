# reelax
> Auto-scroll Instagram Reels while you code.

[![Version](https://img.shields.io/badge/version-0.1.0-cyan.svg)](https://github.com/phnxsahil/reelax)
[![Build](https://img.shields.io/badge/build-stable-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`reelax` is an ambient flow-state tool for developers. It automates your Instagram Reels scrolling on a connected Android device, intelligently pausing whenever you type on your computer and resuming when you're idle.

---

## Features

- **Smart Typing Detection**: Instantly pauses the scroll timer when you are typing.
- **Fast Ad Skipping**: Uses `dumpsys` activity analysis to skip "Sponsored" content in ~100ms.
- **Keyword Filtering**: Automatically skips reels containing blocked keywords (e.g., politics, crypto).
- **Mirroring**: Pinned, always-on-top screen mirroring via `scrcpy` with audio support.
- **Terminal Hotkeys**: Control volume, like, and save reels directly from your CLI.

## Installation

### Prerequisites
- Android device with USB Debugging enabled.
- Python 3.10+

### Quick Setup

**Windows**
```bash
git clone https://github.com/phnxsahil/reelax.git
cd reelax
.\install.bat
```

**Mac / Linux**
```bash
git clone https://github.com/phnxsahil/reelax.git
cd reelax
chmod +x install.sh
./install.sh
```

## Usage

Run the dashboard:
```bash
reelax
```

```text
                  _            
  _ __ ___  ___ | | __ ___  __
 | '__/ _ \/ _ \| |/ _` \ \/ /
 | | |  __/  __/| | (_| |>  < 
 |_|  \___|\___|_|\__,_/_/\_\

  ● Device: Connected
  ● Screen mirror: Ready
```

### In-Session Hotkeys
| Key | Action |
| --- | --- |
| `n` | Skip to next reel |
| `l` | Like reel (Double tap) |
| `s` | Save reel |
| `+` | Volume Up |
| `-` | Volume Down |
| `q` | Quit session |

## Customization
Press `7` in the menu to configure:
- **Blocklist**: Add comma-separated keywords to auto-skip.
- **Cadence**: Adjust scroll intervals (Slow/Medium/Fast).
- **WiFi**: Connect to your device wirelessly.

---

## License
MIT © [phnxsahil](https://github.com/phnxsahil)
