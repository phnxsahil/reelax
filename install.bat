@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo               reelax Setup (Windows)
echo ===================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found. Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    echo [!] Please restart your terminal and run install.bat again.
    exit /b 1
) else (
    echo [OK] Python is installed.
)

:: Check for ADB
adb --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ADB not found. Installing Android Platform Tools via winget...
    winget install Google.PlatformTools --silent --accept-package-agreements --accept-source-agreements
    echo [OK] ADB installed.
) else (
    echo [OK] ADB is installed.
)

:: Check for scrcpy
scrcpy --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] scrcpy not found. Installing scrcpy via winget...
    winget install Genymobile.scrcpy --silent --accept-package-agreements --accept-source-agreements
    echo [OK] scrcpy installed.
) else (
    echo [OK] scrcpy is installed.
)

echo.
echo Installing reelax package...
python -m pip install --upgrade pip
python -m pip install .

echo.
echo ===================================================
echo [SUCCESS] reelax is installed!
echo To start the dashboard, simply type: reelax
echo ===================================================
pause
