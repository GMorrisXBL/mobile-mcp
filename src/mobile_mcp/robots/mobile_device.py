"""MobileDevice robot implementation using mobilecli."""

import json
from typing import Any, Optional

from mobile_mcp.logger import trace
from mobile_mcp.robots.base import (
    ActionableError,
    BaseRobot,
    InstalledApp,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)
from mobile_mcp.utils.subprocess_utils import get_mobilecli_path, run_command, run_command_raw


class MobileDeviceRobot(BaseRobot):
    """Robot implementation using mobilecli for cross-platform device control."""

    def __init__(self, device_id: str):
        """Initialize MobileDevice robot.

        Args:
            device_id: Device identifier.
        """
        self.device_id = device_id
        self._mobilecli_path: Optional[str] = None

    @property
    def mobilecli_path(self) -> str:
        """Get cached mobilecli path."""
        if self._mobilecli_path is None:
            path = get_mobilecli_path()
            if not path:
                raise ActionableError(
                    "mobilecli is not available. "
                    "Please install it from https://github.com/mobile-next/mobile-mcp/wiki"
                )
            self._mobilecli_path = path
        return self._mobilecli_path

    async def _run(self, *args: str, timeout: float = 30.0) -> str:
        """Run a mobilecli command.

        Args:
            *args: Command arguments.
            timeout: Command timeout.

        Returns:
            Command stdout.
        """
        full_args = [*args, "--device", self.device_id]
        stdout, _ = await run_command(self.mobilecli_path, *full_args, timeout=timeout)
        return stdout

    async def _run_json(self, *args: str) -> dict[str, Any]:
        """Run a mobilecli command and parse JSON output."""
        output = await self._run(*args)
        return json.loads(output)

    async def _run_raw(self, *args: str, timeout: float = 30.0) -> bytes:
        """Run a mobilecli command and return raw bytes."""
        full_args = [*args, "--device", self.device_id]
        return await run_command_raw(self.mobilecli_path, *full_args, timeout=timeout)

    async def get_screen_size(self) -> ScreenSize:
        """Get screen dimensions."""
        response = await self._run_json("device", "info")
        screen_size = response.get("data", {}).get("device", {}).get("screenSize", {})
        return ScreenSize(
            width=screen_size.get("width", 0),
            height=screen_size.get("height", 0),
            scale=screen_size.get("scale", 1.0),
        )

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        return await self._run_raw(
            "screenshot", "--format", "png", "--output", "-"
        )

    async def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        await self._run("io", "tap", f"{x},{y}")

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at coordinates."""
        # mobilecli doesn't have native doubletap, so we do two taps
        await self.tap(x, y)
        await self.tap(x, y)

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at coordinates."""
        await self._run("io", "longpress", f"{x},{y}", "--duration", str(duration_ms))

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from center of screen."""
        screen_size = await self.get_screen_size()
        center_x = screen_size.width // 2
        center_y = screen_size.height // 2
        distance = 400

        start_x, start_y = center_x, center_y
        end_x, end_y = center_x, center_y

        if direction == SwipeDirection.UP:
            start_y = center_y + distance // 2
            end_y = center_y - distance // 2
        elif direction == SwipeDirection.DOWN:
            start_y = center_y - distance // 2
            end_y = center_y + distance // 2
        elif direction == SwipeDirection.LEFT:
            start_x = center_x + distance // 2
            end_x = center_x - distance // 2
        elif direction == SwipeDirection.RIGHT:
            start_x = center_x - distance // 2
            end_x = center_x + distance // 2

        await self._run("io", "swipe", f"{start_x},{start_y},{end_x},{end_y}")

    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int | None = None
    ) -> None:
        """Swipe from specific coordinates."""
        swipe_distance = distance or 400
        end_x, end_y = x, y

        if direction == SwipeDirection.UP:
            end_y = y - swipe_distance
        elif direction == SwipeDirection.DOWN:
            end_y = y + swipe_distance
        elif direction == SwipeDirection.LEFT:
            end_x = x - swipe_distance
        elif direction == SwipeDirection.RIGHT:
            end_x = x + swipe_distance

        await self._run("io", "swipe", f"{x},{y},{end_x},{end_y}")

    async def send_keys(self, text: str) -> None:
        """Type text."""
        await self._run("io", "text", text)

    async def press_button(self, button: str) -> None:
        """Press a hardware button."""
        await self._run("io", "button", button)

    async def list_apps(self) -> list[InstalledApp]:
        """List installed apps."""
        response = await self._run_json("apps", "list")
        apps = []
        for app in response.get("data", []):
            apps.append(InstalledApp(
                app_name=app.get("appName", app.get("packageName", "")),
                package_name=app.get("packageName", ""),
            ))
        return apps

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an app by package name."""
        args = ["apps", "launch", package_name]
        if locale:
            args.extend(["--locale", locale])
        await self._run(*args)

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running app."""
        await self._run("apps", "terminate", package_name)

    async def install_app(self, path: str) -> None:
        """Install an app."""
        await self._run("apps", "install", path)

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an app."""
        await self._run("apps", "uninstall", bundle_id)

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        await self._run("url", url)

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get UI elements on screen."""
        response = await self._run_json("dump", "ui")
        elements = []
        for elem in response.get("data", {}).get("elements", []):
            rect_data = elem.get("rect", {})
            elements.append(ScreenElement(
                type=elem.get("type", ""),
                rect=Rect(
                    x=rect_data.get("x", 0),
                    y=rect_data.get("y", 0),
                    width=rect_data.get("width", 0),
                    height=rect_data.get("height", 0),
                ),
                label=elem.get("label"),
                text=elem.get("text"),
                name=elem.get("name"),
                value=elem.get("value"),
                identifier=elem.get("identifier"),
                focused=elem.get("focused", False),
            ))
        return elements

    async def get_orientation(self) -> Orientation:
        """Get current screen orientation."""
        response = await self._run_json("device", "orientation", "get")
        orientation = response.get("data", {}).get("orientation", "portrait")
        return Orientation(orientation)

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set screen orientation."""
        await self._run("device", "orientation", "set", orientation.value)
