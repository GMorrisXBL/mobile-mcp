"""iOS Simulator robot implementation using simctl and WebDriverAgent."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from mobile_mcp.clients.wda import WebDriverAgent
from mobile_mcp.logger import trace
from mobile_mcp.robots.base import (
    ActionableError,
    BaseRobot,
    InstalledApp,
    Orientation,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)
from mobile_mcp.utils.subprocess_utils import run_command, run_command_raw


WDA_PORT = 8100


class SimulatorRobot(BaseRobot):
    """Robot implementation for iOS Simulators using simctl and WebDriverAgent."""

    def __init__(self, simulator_uuid: str):
        """Initialize Simulator robot.

        Args:
            simulator_uuid: Simulator UUID.
        """
        self.simulator_uuid = simulator_uuid
        self._wda: Optional[WebDriverAgent] = None

    async def _simctl(self, *args: str, timeout: float = 30.0) -> str:
        """Run a simctl command.

        Args:
            *args: simctl command arguments.
            timeout: Command timeout.

        Returns:
            Command stdout.
        """
        stdout, _ = await run_command("xcrun", "simctl", *args, timeout=timeout)
        return stdout

    async def _simctl_raw(self, *args: str, timeout: float = 30.0) -> bytes:
        """Run a simctl command and return raw bytes.

        Args:
            *args: simctl command arguments.
            timeout: Command timeout.

        Returns:
            Raw stdout bytes.
        """
        return await run_command_raw("xcrun", "simctl", *args, timeout=timeout)

    async def _is_wda_installed(self) -> bool:
        """Check if WebDriverAgent is installed on the simulator."""
        apps = await self.list_apps()
        return any(app.package_name == "com.facebook.WebDriverAgentRunner.xctrunner" for app in apps)

    async def _start_wda(self) -> None:
        """Start WebDriverAgent on the simulator."""
        if not await self._is_wda_installed():
            trace("WebDriverAgent is not installed on simulator")
            return

        trace("Starting WebDriverAgent")
        wda_package = "com.facebook.WebDriverAgentRunner.xctrunner"

        try:
            await self._simctl("launch", self.simulator_uuid, wda_package)
        except ActionableError:
            trace("Failed to launch WebDriverAgent")
            return

        # Wait for WDA to start (up to 10 seconds)
        wda = WebDriverAgent("localhost", WDA_PORT)
        timeout = asyncio.get_event_loop().time() + 10

        while asyncio.get_event_loop().time() < timeout:
            if await wda.is_running():
                trace("WebDriverAgent is now running")
                return
            await asyncio.sleep(0.1)

        trace("Could not start WebDriverAgent in time")

    async def _get_wda(self) -> WebDriverAgent:
        """Get or start WebDriverAgent.

        Returns:
            WebDriverAgent client.

        Raises:
            ActionableError: If WDA cannot be started.
        """
        wda = WebDriverAgent("localhost", WDA_PORT)

        if not await wda.is_running():
            await self._start_wda()
            if not await wda.is_running():
                raise ActionableError(
                    "WebDriverAgent is not running on simulator. "
                    "Please see https://github.com/mobile-next/mobile-mcp/wiki/"
                )

        return wda

    async def get_screen_size(self) -> ScreenSize:
        """Get screen dimensions."""
        wda = await self._get_wda()
        return await wda.get_screen_size()

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        wda = await self._get_wda()
        return await wda.get_screenshot()

    async def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        wda = await self._get_wda()
        await wda.tap(x, y)

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at coordinates."""
        wda = await self._get_wda()
        await wda.double_tap(x, y)

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at coordinates."""
        wda = await self._get_wda()
        await wda.long_press(x, y, duration_ms)

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from center of screen."""
        wda = await self._get_wda()
        await wda.swipe(direction)

    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int | None = None
    ) -> None:
        """Swipe from specific coordinates."""
        wda = await self._get_wda()
        await wda.swipe_from_coordinate(x, y, direction, distance or 400)

    async def send_keys(self, text: str) -> None:
        """Type text."""
        wda = await self._get_wda()
        await wda.send_keys(text)

    async def press_button(self, button: str) -> None:
        """Press a hardware button."""
        wda = await self._get_wda()
        await wda.press_button(button)

    async def list_apps(self) -> list[InstalledApp]:
        """List installed apps."""
        # Get plist output from simctl
        plist_output = await self._simctl("listapps", self.simulator_uuid)

        # Convert plist to JSON using plutil
        process = await asyncio.create_subprocess_exec(
            "plutil", "-convert", "json", "-o", "-", "-r", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate(plist_output.encode())

        apps_dict = json.loads(stdout.decode())
        apps = []
        for app_info in apps_dict.values():
            apps.append(InstalledApp(
                app_name=app_info.get("CFBundleDisplayName", app_info.get("CFBundleName", "")),
                package_name=app_info.get("CFBundleIdentifier", ""),
            ))

        return apps

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an app by bundle ID."""
        args = ["launch", self.simulator_uuid, package_name]

        if locale:
            locales = [l.strip() for l in locale.split(",")]
            args.extend(["-AppleLanguages", f"({', '.join(locales)})"])
            args.extend(["-AppleLocale", locales[0]])

        await self._simctl(*args)

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running app."""
        await self._simctl("terminate", self.simulator_uuid, package_name)

    async def install_app(self, path: str) -> None:
        """Install an app (.app directory or .zip file)."""
        temp_dir: Optional[str] = None
        install_path = path

        try:
            # Handle .zip files
            if path.lower().endswith(".zip"):
                trace("Detected .zip file, extracting")

                # Validate zip contents (security check)
                await self._validate_zip_paths(path)

                # Extract to temp directory
                temp_dir = tempfile.mkdtemp(prefix="ios-app-")
                await run_command("unzip", "-q", path, "-d", temp_dir)

                # Find .app bundle
                app_bundle = self._find_app_bundle(temp_dir)
                if not app_bundle:
                    raise ActionableError(
                        "No .app bundle found in the .zip file. "
                        "See https://github.com/mobile-next/mobile-mcp/wiki"
                    )

                install_path = app_bundle
                trace(f"Found .app bundle: {os.path.basename(app_bundle)}")

            # Install the app
            await self._simctl("install", self.simulator_uuid, install_path)

        finally:
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    trace(f"Warning: Failed to cleanup temp directory: {e}")

    async def _validate_zip_paths(self, zip_path: str) -> None:
        """Validate zip file doesn't contain path traversal attacks."""
        stdout, _ = await run_command("/usr/bin/zipinfo", "-1", zip_path)

        for line in stdout.split("\n"):
            line = line.strip()
            if line and (line.startswith("/") or ".." in line):
                raise ActionableError(
                    f"Security violation: File path '{line}' contains invalid characters"
                )

    def _find_app_bundle(self, directory: str) -> Optional[str]:
        """Find .app bundle in directory."""
        for entry in os.listdir(directory):
            if entry.endswith(".app"):
                return os.path.join(directory, entry)
        return None

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an app."""
        await self._simctl("uninstall", self.simulator_uuid, bundle_id)

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        wda = await self._get_wda()
        await wda.open_url(url)

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get UI elements on screen."""
        wda = await self._get_wda()
        return await wda.get_elements_on_screen()

    async def get_orientation(self) -> Orientation:
        """Get current screen orientation."""
        wda = await self._get_wda()
        return await wda.get_orientation()

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set screen orientation."""
        wda = await self._get_wda()
        await wda.set_orientation(orientation)
