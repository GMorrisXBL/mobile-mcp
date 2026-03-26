"""Device resolver for finding and creating robot instances."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

from ..robots.base import ActionableError, Robot
from ..robots.android import AndroidRobot
from ..robots.ios import IosRobot
from ..robots.simulator import SimulatorRobot
from ..robots.browserstack import BrowserStackRobot
from ..clients.browserstack_api import BrowserStackCredentials, BrowserStackClient
from .android_manager import AndroidDeviceManager
from .ios_manager import IosManager

if TYPE_CHECKING:
    from ..robots.mobile_device import MobileDeviceRobot


DevicePlatform = Literal["ios", "android"]
DeviceType = Literal["real", "emulator", "simulator", "browserstack"]


@dataclass
class DeviceInfo:
    """Information about a discovered device."""

    id: str
    name: str
    platform: DevicePlatform
    device_type: DeviceType
    version: str
    state: Literal["online", "offline"] = "online"


class DeviceResolver:
    """Resolves device IDs to appropriate Robot implementations.

    Supports:
    - Android physical devices and emulators (via adb)
    - iOS physical devices (via go-ios)
    - iOS simulators (via simctl or mobilecli if available)
    - BrowserStack cloud devices
    """

    def __init__(
        self,
        mobilecli_available: bool = False,
        browserstack_sessions: dict[str, BrowserStackRobot] | None = None,
    ) -> None:
        """Initialize device resolver.

        Args:
            mobilecli_available: Whether mobilecli tool is available
            browserstack_sessions: Dict mapping session IDs to BrowserStack robots
        """
        self.mobilecli_available = mobilecli_available
        self.browserstack_sessions = browserstack_sessions or {}
        self._android_manager = AndroidDeviceManager()
        self._ios_manager = IosManager()

    def get_robot(self, device_id: str) -> Robot:
        """Get a Robot instance for the given device ID.

        Args:
            device_id: Device identifier

        Returns:
            Robot instance for controlling the device

        Raises:
            ActionableError: If device is not found
        """
        # Check if it's a BrowserStack session
        if device_id.startswith("browserstack-session:"):
            session_id = device_id.replace("browserstack-session:", "")
            robot = self.browserstack_sessions.get(session_id)
            if robot:
                return robot
            raise ActionableError(
                f'BrowserStack session "{session_id}" not found. '
                "Use browserstack_start_session to create a session first."
            )

        # Check for iOS physical device
        ios_devices = self._ios_manager.list_devices()
        for device in ios_devices:
            if device.device_id == device_id:
                return IosRobot(device_id)

        # Check for Android device
        android_devices = self._android_manager.get_connected_devices()
        for device in android_devices:
            if device.device_id == device_id:
                return AndroidRobot(device_id)

        # Check for iOS simulator (direct simctl)
        if self._is_simulator(device_id):
            return SimulatorRobot(device_id)

        # If mobilecli is available, try that as a fallback
        if self.mobilecli_available:
            # Dynamic import to avoid circular imports
            from ..robots.mobile_device import MobileDeviceRobot
            return MobileDeviceRobot(device_id)

        raise ActionableError(
            f'Device "{device_id}" not found. '
            "Use the mobile_list_available_devices tool to see available devices."
        )

    def _is_simulator(self, device_id: str) -> bool:
        """Check if device ID corresponds to a booted iOS simulator.

        Args:
            device_id: Device identifier

        Returns:
            True if device is a booted simulator
        """
        from ..utils.subprocess_utils import run_command_sync

        try:
            result = run_command_sync(
                ["xcrun", "simctl", "list", "devices", "booted", "-j"],
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout:
                return False

            import json
            data = json.loads(result.stdout)
            devices = data.get("devices", {})

            for runtime_devices in devices.values():
                for device in runtime_devices:
                    if device.get("udid") == device_id and device.get("state") == "Booted":
                        return True

            return False
        except Exception:
            return False

    def list_devices(self) -> list[DeviceInfo]:
        """List all available devices.

        Returns:
            List of available devices from all sources
        """
        devices: list[DeviceInfo] = []

        # Get Android devices
        try:
            android_devices = self._android_manager.get_connected_devices_with_details()
            for device in android_devices:
                devices.append(
                    DeviceInfo(
                        id=device.device_id,
                        name=device.name,
                        platform="android",
                        device_type="emulator",  # adb doesn't distinguish
                        version=device.version,
                        state="online",
                    )
                )
        except Exception:
            pass

        # Get iOS physical devices
        try:
            ios_devices = self._ios_manager.list_devices_with_details()
            for device in ios_devices:
                devices.append(
                    DeviceInfo(
                        id=device.device_id,
                        name=device.device_name,
                        platform="ios",
                        device_type="real",
                        version=device.version,
                        state="online",
                    )
                )
        except Exception:
            pass

        # Get iOS simulators (via simctl)
        try:
            simulator_devices = self._list_simulators()
            devices.extend(simulator_devices)
        except Exception:
            pass

        return devices

    def _list_simulators(self) -> list[DeviceInfo]:
        """List booted iOS simulators.

        Returns:
            List of booted simulator devices
        """
        from ..utils.subprocess_utils import run_command_sync
        import json

        try:
            result = run_command_sync(
                ["xcrun", "simctl", "list", "devices", "booted", "-j"],
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout:
                return []

            data = json.loads(result.stdout)
            devices_by_runtime = data.get("devices", {})

            simulators = []
            for runtime, runtime_devices in devices_by_runtime.items():
                # Extract iOS version from runtime string
                # e.g., "com.apple.CoreSimulator.SimRuntime.iOS-17-2" -> "17.2"
                version = "unknown"
                if "iOS-" in runtime:
                    version_part = runtime.split("iOS-")[-1]
                    version = version_part.replace("-", ".")

                for device in runtime_devices:
                    if device.get("state") == "Booted":
                        simulators.append(
                            DeviceInfo(
                                id=device.get("udid", ""),
                                name=device.get("name", "Unknown"),
                                platform="ios",
                                device_type="simulator",
                                version=version,
                                state="online",
                            )
                        )

            return simulators
        except Exception:
            return []

    def register_browserstack_session(
        self,
        session_id: str,
        robot: BrowserStackRobot,
    ) -> str:
        """Register a BrowserStack session.

        Args:
            session_id: Session ID from BrowserStack
            robot: BrowserStack robot instance

        Returns:
            Full device ID for use with get_robot
        """
        self.browserstack_sessions[session_id] = robot
        return f"browserstack-session:{session_id}"

    def unregister_browserstack_session(self, session_id: str) -> bool:
        """Unregister a BrowserStack session.

        Args:
            session_id: Session ID to remove

        Returns:
            True if session was found and removed
        """
        # Handle both formats
        if session_id.startswith("browserstack-session:"):
            session_id = session_id.replace("browserstack-session:", "")

        if session_id in self.browserstack_sessions:
            del self.browserstack_sessions[session_id]
            return True
        return False

    def list_browserstack_sessions(self) -> list[str]:
        """List active BrowserStack session IDs.

        Returns:
            List of session IDs
        """
        return list(self.browserstack_sessions.keys())
