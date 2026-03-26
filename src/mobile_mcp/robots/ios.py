"""iOS real device robot implementation using go-ios and WebDriverAgent."""

import asyncio
import json
import socket
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
from mobile_mcp.utils.subprocess_utils import get_go_ios_path, run_command


WDA_PORT = 8100
IOS_TUNNEL_PORT = 60105


class IosRobot(BaseRobot):
    """Robot implementation for iOS real devices using go-ios and WebDriverAgent."""

    def __init__(self, device_id: str):
        """Initialize iOS robot.

        Args:
            device_id: iOS device UDID.
        """
        self.device_id = device_id
        self._go_ios_path: Optional[str] = None

    @property
    def go_ios_path(self) -> str:
        """Get cached go-ios path."""
        if self._go_ios_path is None:
            self._go_ios_path = get_go_ios_path()
        return self._go_ios_path

    async def _ios(self, *args: str, timeout: float = 30.0) -> str:
        """Run a go-ios command.

        Args:
            *args: go-ios command arguments.
            timeout: Command timeout.

        Returns:
            Command stdout.
        """
        stdout, _ = await run_command(
            self.go_ios_path, "--udid", self.device_id, *args,
            timeout=timeout,
        )
        return stdout

    def _is_port_listening(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is listening.

        Args:
            port: Port number.
            host: Host to connect to.

        Returns:
            True if port is listening.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception:
            return False

    async def _is_tunnel_running(self) -> bool:
        """Check if iOS tunnel is running."""
        return self._is_port_listening(IOS_TUNNEL_PORT)

    async def _is_wda_forward_running(self) -> bool:
        """Check if WDA port forwarding is running."""
        return self._is_port_listening(WDA_PORT)

    async def _get_ios_version(self) -> str:
        """Get iOS version."""
        output = await self._ios("info")
        data = json.loads(output)
        return data.get("ProductVersion", "0")

    async def _is_tunnel_required(self) -> bool:
        """Check if tunnel is required (iOS 17+)."""
        version = await self._get_ios_version()
        major = int(version.split(".")[0])
        return major >= 17

    async def _assert_tunnel_running(self) -> None:
        """Assert that iOS tunnel is running if required.

        Raises:
            ActionableError: If tunnel is required but not running.
        """
        if await self._is_tunnel_required():
            if not await self._is_tunnel_running():
                raise ActionableError(
                    "iOS tunnel is not running. "
                    "Please see https://github.com/mobile-next/mobile-mcp/wiki/"
                )

    async def _get_wda(self) -> WebDriverAgent:
        """Get WebDriverAgent client.

        Returns:
            WebDriverAgent client.

        Raises:
            ActionableError: If WDA is not accessible.
        """
        await self._assert_tunnel_running()

        if not await self._is_wda_forward_running():
            raise ActionableError(
                "Port forwarding to WebDriverAgent is not running. "
                "Please see https://github.com/mobile-next/mobile-mcp/wiki/"
            )

        wda = WebDriverAgent("localhost", WDA_PORT)

        if not await wda.is_running():
            raise ActionableError(
                "WebDriverAgent is not running on device. "
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
        await self._assert_tunnel_running()

        output = await self._ios("apps", "--all", "--list")
        apps = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) >= 1:
                package_name = parts[0]
                app_name = parts[1] if len(parts) > 1 else package_name
                apps.append(InstalledApp(app_name=app_name, package_name=package_name))

        return apps

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an app by bundle ID."""
        await self._assert_tunnel_running()

        args = ["launch", package_name]
        if locale:
            locales = [l.strip() for l in locale.split(",")]
            args.extend(["-AppleLanguages", f"({', '.join(locales)})"])
            args.extend(["-AppleLocale", locales[0]])

        await self._ios(*args)

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running app."""
        await self._assert_tunnel_running()
        await self._ios("kill", package_name)

    async def install_app(self, path: str) -> None:
        """Install an IPA file."""
        await self._assert_tunnel_running()
        await self._ios("install", "--path", path)

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an app."""
        await self._assert_tunnel_running()
        await self._ios("uninstall", "--bundleid", bundle_id)

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

    async def get_logs(
        self, filter_text: str | None = None, lines: int = 100, level: str | None = None
    ) -> str:
        """Get device syslog."""
        await self._assert_tunnel_running()

        # go-ios syslog streams continuously, so we use timeout
        try:
            process = await asyncio.create_subprocess_exec(
                "timeout", "1",
                self.go_ios_path, "syslog", "--udid", self.device_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
            output = stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return ""
        except Exception as e:
            trace(f"Failed to get iOS logs: {e}")
            return ""

        log_lines = output.split("\n")

        # Filter by process name if specified
        if filter_text:
            log_lines = [
                line for line in log_lines
                if filter_text.lower() in line.lower()
            ]

        # Return last N lines
        return "\n".join(log_lines[-lines:])
