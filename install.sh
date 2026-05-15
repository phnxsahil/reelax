#!/bin/bash
set -e

echo "==================================================="
echo "              reelax Setup (Mac/Linux)"
echo "==================================================="
echo ""

# Find the best python version
PYTHON_CMD="python3"
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
fi

# Check for Python and its version
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "[!] No suitable python3 found. Please install Python 3.10+ to continue."
    exit 1
else
    PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if awk 'BEGIN {exit !('"$PY_VERSION"' < 3.10)}'; then
        echo "[!] Your Python version ($PY_VERSION) is too old. reelax requires Python 3.10 or newer."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Since you are on Mac, you can upgrade by running: brew install python@3.12"
        fi
        exit 1
    else
        echo "[OK] Using $PYTHON_CMD (version $PY_VERSION)."
    fi
fi

# Check for Homebrew (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &> /dev/null; then
        echo "[!] Homebrew not found. Required for Mac dependencies."
        echo "Install it: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
fi

# Check for ADB
if ! command -v adb &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Installing ADB via Homebrew..."
        brew install android-platform-tools
    else
        echo "Please install ADB (e.g. sudo apt install adb)"
        exit 1
    fi
fi

# Check for scrcpy
if ! command -v scrcpy &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Installing scrcpy via Homebrew..."
        brew install scrcpy
    fi
fi

# Determine if we need --break-system-packages (macOS PEP 668)
EXTRA_FLAGS=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    EXTRA_FLAGS="--break-system-packages"
fi

echo ""
echo "Installing reelax package..."
$PYTHON_CMD -m pip install --upgrade pip $EXTRA_FLAGS || true
$PYTHON_CMD -m pip install . $EXTRA_FLAGS

echo ""
echo "==================================================="
echo "[SUCCESS] reelax is installed!"
echo "To start, type: reelax"
echo "Note: If 'reelax' command is not found, you may need to add the Python bin folder to your PATH."
echo "==================================================="
