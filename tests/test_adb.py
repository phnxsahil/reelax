import pytest
from unittest.mock import patch, MagicMock
from reelax.core.adb import list_devices, connect_device, ADBDevice
from reelax.core.exceptions import DeviceNotFoundError, ADBNotInstalledError

def test_list_devices_parsing():
    mock_output = "List of devices attached\n988a1b4a4c4e344a\tdevice\nemulator-5554\tdevice\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        devices = list_devices()
        assert devices == ["988a1b4a4c4e344a", "emulator-5554"]

def test_connect_device_auto_select():
    mock_output = "List of devices attached\n988a1b4a4c4e344a\tdevice\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        device = connect_device()
        assert device.serial == "988a1b4a4c4e344a"

def test_connect_device_not_found():
    mock_output = "List of devices attached\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        with pytest.raises(DeviceNotFoundError):
            connect_device()

def test_swipe_calls_correct_args():
    device = ADBDevice(serial="test-serial")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        device.swipe(x=500, y_start=1600, y_end=300, duration_ms=500)
        
        expected_cmd = [
            "adb", "-s", "test-serial",
            "shell", "input swipe 500 1600 500 300 500"
        ]
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == expected_cmd
