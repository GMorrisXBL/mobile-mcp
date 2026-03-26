"""iOS device manager for discovering connected devices."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ..utils.subprocess_utils import run_command_sync


def get_go_ios_path() -> str:
    """Get path to go-ios executable.

    Checks GO_IOS_PATH environment variable, falls back to 'ios' in PATH.
    """
    return os.environ.get("GO_IOS_PATH", "ios")


@dataclass
class IosDevice:
    """Connected iOS device information."""

    device_id: str
    device_name: str


@dataclass
class IosDeviceDetails(IosDevice):
    """iOS device with additional details."""

    version: str


@dataclass
class IosDeviceInfo:
    """Full device info from go-ios."""

    device_class: str
    device_name: str
    product_name: str
    product_type: str
    product_version: str
    phone_number: str | None
    time_zone: str


class IosManager:
    """Manages discovery and information retrieval for iOS physical devices.

    Uses go-ios CLI (https://github.com/danielpaulus/go-ios) for device interaction.
    """

    def __init__(self) -> None:
        """Initialize the iOS device manager."""
        self.ios_path = get_go_ios_path()

    def _run_ios(self, *args: str, timeout: int = 10) -> str:
        """Run a go-ios command.

        Args:
            *args: Command arguments
            timeout: Command timeout in seconds

        Returns:
            Command stdout as string
        """
        cmd = [self.ios_path, *args]
        result = run_command_sync(cmd, timeout=timeout)
        return result.stdout.strip() if result.stdout else ""

    def is_go_ios_installed(self) -> bool:
        """Check if go-ios is installed and working.

        Returns:
            True if go-ios is available
        """
        try:
            output = self._run_ios("version")
            data = json.loads(output)
            version = data.get("version", "")
            return version.startswith("v") or version == "local-build"
        except Exception:
            return False

    def get_device_name(self, device_id: str) -> str:
        """Get device name for a specific device.

        Args:
            device_id: Device UDID

        Returns:
            Device name
        """
        output = self._run_ios("info", "--udid", device_id)
        data = json.loads(output)
        return data.get("DeviceName", device_id)

    def get_device_info(self, device_id: str) -> IosDeviceInfo:
        """Get full device info for a specific device.

        Args:
            device_id: Device UDID

        Returns:
            IosDeviceInfo with all device details
        """
        output = self._run_ios("info", "--udid", device_id)
        data = json.loads(output)
        return IosDeviceInfo(
            device_class=data.get("DeviceClass", ""),
            device_name=data.get("DeviceName", ""),
            product_name=data.get("ProductName", ""),
            product_type=data.get("ProductType", ""),
            product_version=data.get("ProductVersion", ""),
            phone_number=data.get("PhoneNumber"),
            time_zone=data.get("TimeZone", ""),
        )

    def list_devices(self) -> list[IosDevice]:
        """List connected iOS physical devices.

        Returns:
            List of connected iOS devices
        """
        if not self.is_go_ios_installed():
            return []

        try:
            output = self._run_ios("list")
            data = json.loads(output)
            device_list = data.get("deviceList", [])

            devices = []
            for device_id in device_list:
                try:
                    device_name = self.get_device_name(device_id)
                    devices.append(
                        IosDevice(device_id=device_id, device_name=device_name)
                    )
                except Exception:
                    devices.append(
                        IosDevice(device_id=device_id, device_name=device_id)
                    )

            return devices
        except Exception:
            return []

    def list_devices_with_details(self) -> list[IosDeviceDetails]:
        """List connected iOS physical devices with full details.

        Returns:
            List of connected devices with version info
        """
        if not self.is_go_ios_installed():
            return []

        try:
            output = self._run_ios("list")
            data = json.loads(output)
            device_list = data.get("deviceList", [])

            devices = []
            for device_id in device_list:
                try:
                    info = self.get_device_info(device_id)
                    devices.append(
                        IosDeviceDetails(
                            device_id=device_id,
                            device_name=info.device_name,
                            version=info.product_version,
                        )
                    )
                except Exception:
                    devices.append(
                        IosDeviceDetails(
                            device_id=device_id,
                            device_name=device_id,
                            version="unknown",
                        )
                    )

            return devices
        except Exception:
            return []
