"""Android device manager for discovering connected devices."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..utils.subprocess_utils import run_command_sync


def get_adb_path() -> str:
    """Get path to adb executable.

    Checks:
    1. ANDROID_HOME environment variable
    2. Default macOS location
    3. Default Windows location
    4. Falls back to 'adb' in PATH
    """
    exe_name = "adb.exe" if os.name == "nt" else "adb"

    # Check ANDROID_HOME
    android_home = os.environ.get("ANDROID_HOME")
    if android_home:
        adb_path = Path(android_home) / "platform-tools" / exe_name
        if adb_path.exists():
            return str(adb_path)

    # Check default macOS location
    if os.name == "posix":
        home = os.environ.get("HOME")
        if home:
            default_path = Path(home) / "Library" / "Android" / "sdk" / "platform-tools" / "adb"
            if default_path.exists():
                return str(default_path)

    # Check default Windows location
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            windows_path = Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
            if windows_path.exists():
                return str(windows_path)

    # Fall back to PATH
    return exe_name


AndroidDeviceType = Literal["tv", "mobile"]


@dataclass
class AndroidDevice:
    """Connected Android device information."""

    device_id: str
    device_type: AndroidDeviceType


@dataclass
class AndroidDeviceDetails(AndroidDevice):
    """Android device with additional details."""

    version: str
    name: str


class AndroidDeviceManager:
    """Manages discovery and information retrieval for Android devices."""

    def __init__(self) -> None:
        """Initialize the Android device manager."""
        self.adb_path = get_adb_path()

    def _run_adb(self, *args: str, device_id: str | None = None, timeout: int = 5) -> str:
        """Run an adb command.

        Args:
            *args: Command arguments
            device_id: Optional device ID to target
            timeout: Command timeout in seconds

        Returns:
            Command stdout as string
        """
        cmd = [self.adb_path]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(args)

        result = run_command_sync(cmd, timeout=timeout)
        return result.stdout.strip() if result.stdout else ""

    def _get_device_type(self, device_id: str) -> AndroidDeviceType:
        """Determine if device is a TV or mobile device.

        Args:
            device_id: Device identifier

        Returns:
            'tv' for Android TV devices, 'mobile' otherwise
        """
        try:
            output = self._run_adb(
                "shell", "pm", "list", "features",
                device_id=device_id,
            )
            features = [
                line.replace("feature:", "")
                for line in output.split("\n")
                if line.startswith("feature:")
            ]

            if "android.software.leanback" in features or "android.hardware.type.television" in features:
                return "tv"
            return "mobile"
        except Exception:
            return "mobile"

    def _get_device_version(self, device_id: str) -> str:
        """Get Android version for a device.

        Args:
            device_id: Device identifier

        Returns:
            Android version string (e.g., "14")
        """
        try:
            return self._run_adb(
                "shell", "getprop", "ro.build.version.release",
                device_id=device_id,
            )
        except Exception:
            return "unknown"

    def _get_device_name(self, device_id: str) -> str:
        """Get device name (model or AVD name).

        Args:
            device_id: Device identifier

        Returns:
            Device name or model
        """
        try:
            # Try getting AVD name first (for emulators)
            avd_name = self._run_adb(
                "shell", "getprop", "ro.boot.qemu.avd_name",
                device_id=device_id,
            )
            if avd_name:
                # Replace underscores with spaces
                return avd_name.replace("_", " ")

            # Fall back to product model
            return self._run_adb(
                "shell", "getprop", "ro.product.model",
                device_id=device_id,
            )
        except Exception:
            return device_id

    def get_connected_devices(self) -> list[AndroidDevice]:
        """Get list of connected Android devices.

        Returns:
            List of connected Android devices
        """
        try:
            output = self._run_adb("devices")
            devices = []

            for line in output.split("\n"):
                line = line.strip()
                if not line or line.startswith("List of devices attached"):
                    continue

                parts = line.split("\t")
                if len(parts) >= 2 and parts[1].strip() == "device":
                    device_id = parts[0]
                    devices.append(
                        AndroidDevice(
                            device_id=device_id,
                            device_type=self._get_device_type(device_id),
                        )
                    )

            return devices
        except Exception:
            return []

    def get_connected_devices_with_details(self) -> list[AndroidDeviceDetails]:
        """Get list of connected Android devices with full details.

        Returns:
            List of connected devices with version and name info
        """
        try:
            output = self._run_adb("devices")
            devices = []

            for line in output.split("\n"):
                line = line.strip()
                if not line or line.startswith("List of devices attached"):
                    continue

                parts = line.split("\t")
                if len(parts) >= 2 and parts[1].strip() == "device":
                    device_id = parts[0]
                    devices.append(
                        AndroidDeviceDetails(
                            device_id=device_id,
                            device_type=self._get_device_type(device_id),
                            version=self._get_device_version(device_id),
                            name=self._get_device_name(device_id),
                        )
                    )

            return devices
        except Exception:
            return []

    def is_adb_available(self) -> bool:
        """Check if adb is available and working.

        Returns:
            True if adb is available
        """
        try:
            self._run_adb("version")
            return True
        except Exception:
            return False
