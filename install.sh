#!/bin/bash
set -e

echo "==================================================="
echo "              reelax Setup (Mac/Linux)"
echo "==================================================="
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[!] python3 not found. Please install Python 3.10+ to continue."
    exit 1
else
    echo "[OK] python3 is installed."
fi

# Check for Homebrew (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &> /dev/null; then
        echo "[!] Homebrew not found. It is required to install system dependencies on Mac."
        echo "Please install it from https://brew.sh or run:"
        echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi
fi

# Check for ADB
if ! command -v adb &> /dev/null; then
    echo "[!] adb not found."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Installing via Homebrew..."
        brew install android-platform-tools
    else
        echo "Please install ADB using your package manager (e.g., sudo apt install adb)"
        exit 1
    fi
else
    echo "[OK] adb is installed."
fi

# Check for scrcpy
if ! command -v scrcpy &> /dev/null; then
    echo "[!] scrcpy not found."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Installing via Homebrew..."
        brew install scrcpy
    else
        echo "Please install scrcpy using your package manager (e.g., sudo apt install scrcpy)"
    fi
else
    echo "[OK] scrcpy is installed."
fi

echo ""
echo "Installing reelax package..."
python3 -m pip install -e .

echo ""
echo "==================================================="
echo "[SUCCESS] reelax is installed!"
echo "To start the dashboard, simply type: reelax"
echo "==================================================="
