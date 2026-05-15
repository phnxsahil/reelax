import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath("."))

try:
    from reelax.core.adb import list_devices
    from reelax.core.exceptions import ADBNotInstalledError
    
    print("Checking for ADB devices...")
    devices = list_devices()
    if not devices:
        print("No devices found. Is your phone connected?")
    else:
        print(f"Found devices: {devices}")
except ADBNotInstalledError:
    print("Error: ADB is not installed or not in your PATH.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
