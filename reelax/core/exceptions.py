"""Custom exceptions for the reelax project."""

class ReelaxError(Exception):
    """Base exception for all reelax errors."""
    pass

class DeviceNotFoundError(ReelaxError):
    """No Android device detected via ADB."""
    def __init__(self, message: str = "No Android device found.\nMake sure your phone is connected via USB and USB Debugging is enabled.\nRun `adb devices` to verify your connection."):
        super().__init__(message)

class ADBNotInstalledError(ReelaxError):
    """ADB binary not found in PATH."""
    def __init__(self, message: str = "ADB binary not found in PATH.\nPlease install Android SDK Platform-Tools or add adb to your PATH."):
        super().__init__(message)

class InstagramNotFoundError(ReelaxError):
    """Instagram app not installed or not open on device."""
    pass

class ScrollFailedError(ReelaxError):
    """ADB swipe command failed."""
    pass

class ConfigValidationError(ReelaxError):
    """Config file has invalid values."""
    pass
