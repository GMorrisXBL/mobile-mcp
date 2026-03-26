"""FastMCP server for mobile automation.

Provides MCP tools for controlling mobile devices (Android, iOS, BrowserStack).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .clients.browserstack_api import (
    BrowserStackClient,
    BrowserStackCredentials,
    is_browserstack_configured,
)
from .logger import get_logger
from .managers.device_resolver import DeviceResolver
from .robots.base import ActionableError, Orientation, SwipeDirection
from .robots.browserstack import BrowserStackRobot
from .utils.image import process_screenshot
from .utils.png import get_png_dimensions
from .utils.validation import validate_file_extension, validate_output_path

logger = get_logger(__name__)

# File extension allowlists
ALLOWED_SCREENSHOT_EXTENSIONS = [".png", ".jpg", ".jpeg"]
ALLOWED_RECORDING_EXTENSIONS = [".mp4"]

# Type aliases for FastMCP annotations
DeviceId = Annotated[
    str,
    Field(
        description="The device identifier. Use mobile_list_available_devices to find available devices."
    ),
]


@dataclass
class ActiveRecording:
    """Tracks an active screen recording."""

    process: asyncio.subprocess.Process
    output_path: str
    started_at: float


def get_version() -> str:
    """Get the package version."""
    try:
        from importlib.metadata import version
        return version("mobile-mcp")
    except Exception:
        return "0.1.0"


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all mobile automation tools.

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name="mobile-mcp",
        version=get_version(),
    )

    # Initialize device resolver and state
    device_resolver = DeviceResolver()
    active_recordings: dict[str, ActiveRecording] = {}

    # BrowserStack client (if configured)
    bs_credentials = BrowserStackCredentials.from_env()
    bs_client = BrowserStackClient(bs_credentials) if bs_credentials else None

    # =====================================
    # Device Discovery Tools
    # =====================================

    @mcp.tool()
    async def mobile_list_available_devices() -> str:
        """List all available devices including physical devices, simulators, and emulators.

        Returns both Android and iOS devices that are currently connected and ready.
        """
        devices = device_resolver.list_devices()
        result = {
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "platform": d.platform,
                    "type": d.device_type,
                    "version": d.version,
                    "state": d.state,
                }
                for d in devices
            ]
        }
        return json.dumps(result)

    # =====================================
    # App Management Tools
    # =====================================

    @mcp.tool()
    async def mobile_list_apps(device: DeviceId) -> str:
        """List all installed apps on the device.

        Args:
            device: The device identifier
        """
        robot = device_resolver.get_robot(device)
        apps = await robot.list_apps()
        app_list = ", ".join(f"{app.app_name} ({app.package_name})" for app in apps)
        return f"Found these apps on device: {app_list}"

    @mcp.tool()
    async def mobile_launch_app(
        device: DeviceId,
        packageName: Annotated[str, Field(description="Package name/bundle ID of the app to launch")],
        locale: Annotated[
            str | None,
            Field(description="Comma-separated BCP 47 locale tags (e.g., fr-FR,en-GB)")
        ] = None,
    ) -> str:
        """Launch an app on the mobile device.

        Use mobile_list_apps to find available package names.
        """
        robot = device_resolver.get_robot(device)
        await robot.launch_app(packageName, locale)
        return f"Launched app {packageName}"

    @mcp.tool()
    async def mobile_terminate_app(
        device: DeviceId,
        packageName: Annotated[str, Field(description="Package name/bundle ID of the app to terminate")],
    ) -> str:
        """Stop and terminate an app on the mobile device."""
        robot = device_resolver.get_robot(device)
        await robot.terminate_app(packageName)
        return f"Terminated app {packageName}"

    @mcp.tool()
    async def mobile_install_app(
        device: DeviceId,
        path: Annotated[
            str,
            Field(
                description="Path to the app file. For iOS simulators: .zip or .app directory. "
                "For Android: .apk file. For iOS real devices: .ipa file."
            ),
        ],
    ) -> str:
        """Install an app on the mobile device."""
        robot = device_resolver.get_robot(device)
        await robot.install_app(path)
        return f"Installed app from {path}"

    @mcp.tool()
    async def mobile_uninstall_app(
        device: DeviceId,
        bundle_id: Annotated[
            str,
            Field(description="Bundle identifier (iOS) or package name (Android) to uninstall"),
        ],
    ) -> str:
        """Uninstall an app from the mobile device."""
        robot = device_resolver.get_robot(device)
        await robot.uninstall_app(bundle_id)
        return f"Uninstalled app {bundle_id}"

    # =====================================
    # Screen Information Tools
    # =====================================

    @mcp.tool()
    async def mobile_get_screen_size(device: DeviceId) -> str:
        """Get the screen size of the mobile device in pixels."""
        robot = device_resolver.get_robot(device)
        screen_size = await robot.get_screen_size()
        return f"Screen size is {screen_size.width}x{screen_size.height} pixels"

    @mcp.tool()
    async def mobile_list_elements_on_screen(device: DeviceId) -> str:
        """List UI elements on screen with their coordinates and text.

        Returns interactive elements that can be tapped. Do not cache this result.
        """
        robot = device_resolver.get_robot(device)
        elements = await robot.get_elements_on_screen()

        result = []
        for element in elements:
            result.append(element.to_dict())

        return f"Found these elements on screen: {json.dumps(result)}"

    @mcp.tool()
    async def mobile_get_orientation(device: DeviceId) -> str:
        """Get the current screen orientation of the device."""
        robot = device_resolver.get_robot(device)
        orientation = await robot.get_orientation()
        return f"Current device orientation is {orientation.value}"

    @mcp.tool()
    async def mobile_set_orientation(
        device: DeviceId,
        orientation: Annotated[
            Literal["portrait", "landscape"],
            Field(description="The desired orientation"),
        ],
    ) -> str:
        """Change the screen orientation of the device."""
        robot = device_resolver.get_robot(device)
        await robot.set_orientation(Orientation(orientation))
        return f"Changed device orientation to {orientation}"

    # =====================================
    # Screenshot Tools
    # =====================================

    @mcp.tool()
    async def mobile_take_screenshot(device: DeviceId) -> list[dict[str, Any]]:
        """Take a screenshot of the mobile device.

        Use this to understand what's on screen. Do not cache this result.
        For finding tappable elements, use mobile_list_elements_on_screen instead.
        """
        robot = device_resolver.get_robot(device)
        screen_size = await robot.get_screen_size()
        screenshot = await robot.get_screenshot()

        # Validate PNG
        try:
            png_size = get_png_dimensions(screenshot)
            if png_size[0] <= 0 or png_size[1] <= 0:
                raise ActionableError("Screenshot is invalid. Please try again.")
        except Exception as e:
            raise ActionableError(f"Screenshot validation failed: {e}")

        # Process screenshot (resize/compress if configured)
        processed, mime_type = process_screenshot(screenshot, int(screen_size.scale))

        logger.debug(f"Screenshot taken: {len(processed)} bytes, {mime_type}")

        return [
            {
                "type": "image",
                "data": base64.b64encode(processed).decode("ascii"),
                "mimeType": mime_type,
            }
        ]

    @mcp.tool()
    async def mobile_save_screenshot(
        device: DeviceId,
        saveTo: Annotated[
            str,
            Field(description="Path to save the screenshot. Must end with .png, .jpg, or .jpeg"),
        ],
    ) -> str:
        """Save a screenshot of the mobile device to a file."""
        validate_file_extension(saveTo, ALLOWED_SCREENSHOT_EXTENSIONS, "save_screenshot")
        validate_output_path(saveTo)

        robot = device_resolver.get_robot(device)
        screenshot = await robot.get_screenshot()

        Path(saveTo).write_bytes(screenshot)
        return f"Screenshot saved to: {saveTo}"

    # =====================================
    # Touch Interaction Tools
    # =====================================

    @mcp.tool()
    async def mobile_click_on_screen_at_coordinates(
        device: DeviceId,
        x: Annotated[int, Field(description="X coordinate in pixels")],
        y: Annotated[int, Field(description="Y coordinate in pixels")],
    ) -> str:
        """Click/tap on the screen at given coordinates.

        Use mobile_list_elements_on_screen to find element coordinates.
        """
        robot = device_resolver.get_robot(device)
        await robot.tap(x, y)
        return f"Clicked on screen at coordinates: {x}, {y}"

    @mcp.tool()
    async def mobile_double_tap_on_screen(
        device: DeviceId,
        x: Annotated[int, Field(description="X coordinate in pixels")],
        y: Annotated[int, Field(description="Y coordinate in pixels")],
    ) -> str:
        """Double-tap on the screen at given coordinates."""
        robot = device_resolver.get_robot(device)
        await robot.double_tap(x, y)
        return f"Double-tapped on screen at coordinates: {x}, {y}"

    @mcp.tool()
    async def mobile_long_press_on_screen_at_coordinates(
        device: DeviceId,
        x: Annotated[int, Field(description="X coordinate in pixels")],
        y: Annotated[int, Field(description="Y coordinate in pixels")],
        duration: Annotated[
            int | None,
            Field(description="Duration in milliseconds (1-10000). Defaults to 500ms.", ge=1, le=10000),
        ] = None,
    ) -> str:
        """Long press on the screen at given coordinates."""
        robot = device_resolver.get_robot(device)
        press_duration = duration or 500
        await robot.long_press(x, y, press_duration)
        return f"Long pressed on screen at coordinates: {x}, {y} for {press_duration}ms"

    @mcp.tool()
    async def mobile_swipe_on_screen(
        device: DeviceId,
        direction: Annotated[
            Literal["up", "down", "left", "right"],
            Field(description="The direction to swipe"),
        ],
        x: Annotated[int | None, Field(description="Starting X coordinate. Uses center if not provided.")] = None,
        y: Annotated[int | None, Field(description="Starting Y coordinate. Uses center if not provided.")] = None,
        distance: Annotated[
            int | None,
            Field(description="Swipe distance in pixels. Defaults to 400px for iOS or 30% of screen for Android."),
        ] = None,
    ) -> str:
        """Swipe on the screen in a direction."""
        robot = device_resolver.get_robot(device)

        if x is not None and y is not None:
            await robot.swipe_from_coordinate(x, y, SwipeDirection(direction), distance)
            distance_text = f" {distance} pixels" if distance else ""
            return f"Swiped {direction}{distance_text} from coordinates: {x}, {y}"
        else:
            await robot.swipe(SwipeDirection(direction))
            return f"Swiped {direction} on screen"

    # =====================================
    # Input Tools
    # =====================================

    @mcp.tool()
    async def mobile_type_keys(
        device: DeviceId,
        text: Annotated[str, Field(description="The text to type")],
        submit: Annotated[bool, Field(description="Whether to press Enter after typing")],
    ) -> str:
        """Type text into the focused element."""
        robot = device_resolver.get_robot(device)
        await robot.send_keys(text)

        if submit:
            await robot.press_button("ENTER")

        return f"Typed text: {text}"

    @mcp.tool()
    async def mobile_press_button(
        device: DeviceId,
        button: Annotated[
            str,
            Field(
                description="Button to press: BACK (Android only), HOME, VOLUME_UP, VOLUME_DOWN, "
                "ENTER, DPAD_CENTER/UP/DOWN/LEFT/RIGHT (Android TV only)"
            ),
        ],
    ) -> str:
        """Press a hardware or software button on the device."""
        robot = device_resolver.get_robot(device)
        await robot.press_button(button)
        return f"Pressed the button: {button}"

    @mcp.tool()
    async def mobile_open_url(
        device: DeviceId,
        url: Annotated[
            str,
            Field(
                description="URL or deep link to open. Supports http/https URLs and custom schemes "
                "(e.g., 'myapp://path', 'fb://profile')"
            ),
        ],
    ) -> str:
        """Open a URL or deep link on the device."""
        robot = device_resolver.get_robot(device)
        await robot.open_url(url)
        return f"Opened URL: {url}"

    # =====================================
    # Log Tools
    # =====================================

    @mcp.tool()
    async def mobile_get_device_logs(
        device: DeviceId,
        filter: Annotated[
            str | None,
            Field(description="Filter by package name (Android) or process name (iOS)"),
        ] = None,
        lines: Annotated[
            int | None,
            Field(description="Number of lines to return (default: 100, max: 1000)", ge=1, le=1000),
        ] = None,
        level: Annotated[
            Literal["V", "D", "I", "W", "E", "F"] | None,
            Field(description="Minimum log level (Android only): V=Verbose, D=Debug, I=Info, W=Warn, E=Error, F=Fatal"),
        ] = None,
    ) -> str:
        """Get device logs (logcat for Android, syslog for iOS).

        Useful for debugging app crashes, errors, and behavior.
        """
        robot = device_resolver.get_robot(device)

        if not hasattr(robot, "get_logs"):
            raise ActionableError(
                "This device does not support log retrieval. "
                "Logs are available for local Android and iOS devices only."
            )

        num_lines = min(lines or 100, 1000)
        logs = await robot.get_logs(filter, num_lines, level)  # type: ignore

        if not logs or not logs.strip():
            if filter:
                return f'No logs found matching filter "{filter}". Try without a filter or check if the app is running.'
            return "No logs found. The log buffer may be empty."

        line_count = len([l for l in logs.split("\n") if l.strip()])
        filter_text = f' matching "{filter}"' if filter else ""
        return f"Found {line_count} log entries{filter_text}:\n\n{logs}"

    @mcp.tool()
    async def mobile_clear_device_logs(device: DeviceId) -> str:
        """Clear the device log buffer.

        Useful before reproducing a bug to get clean logs.
        Only supported on Android devices.
        """
        robot = device_resolver.get_robot(device)

        if not hasattr(robot, "clear_logs"):
            raise ActionableError(
                "This device does not support clearing logs. "
                "Log clearing is available for Android devices only."
            )

        await robot.clear_logs()  # type: ignore
        return "Device log buffer cleared successfully. New logs will now only contain events from this point forward."

    # =====================================
    # Screen Recording Tools
    # =====================================

    @mcp.tool()
    async def mobile_start_screen_recording(
        device: DeviceId,
        output: Annotated[
            str | None,
            Field(description="File path to save recording. Must end with .mp4. Uses temp file if not provided."),
        ] = None,
        timeLimit: Annotated[
            int | None,
            Field(description="Maximum recording duration in seconds. Recording stops automatically after this time."),
        ] = None,
    ) -> str:
        """Start recording the screen of a mobile device.

        The recording runs in background until stopped with mobile_stop_screen_recording.
        """
        if output:
            validate_file_extension(output, ALLOWED_RECORDING_EXTENSIONS, "start_screen_recording")
            validate_output_path(output)

        # Verify device exists
        device_resolver.get_robot(device)

        if device in active_recordings:
            raise ActionableError(
                f'Device "{device}" is already being recorded. '
                "Stop the current recording first with mobile_stop_screen_recording."
            )

        output_path = output or str(Path(tempfile.gettempdir()) / f"screen-recording-{int(asyncio.get_event_loop().time() * 1000)}.mp4")

        # Note: Screen recording requires mobilecli or platform-specific tools
        # This is a simplified implementation
        raise ActionableError(
            "Screen recording is not yet implemented in the Python version. "
            "Use the TypeScript version for screen recording support."
        )

    @mcp.tool()
    async def mobile_stop_screen_recording(device: DeviceId) -> str:
        """Stop an active screen recording on a mobile device.

        Returns the file path, size, and approximate duration of the recording.
        """
        recording = active_recordings.get(device)
        if not recording:
            raise ActionableError(
                f'No active recording found for device "{device}". '
                "Start a recording first with mobile_start_screen_recording."
            )

        # Stop the recording process
        del active_recordings[device]
        recording.process.terminate()

        try:
            await asyncio.wait_for(recording.process.wait(), timeout=300)
        except asyncio.TimeoutError:
            recording.process.kill()

        output_path = Path(recording.output_path)
        if not output_path.exists():
            duration = int((asyncio.get_event_loop().time() - recording.started_at))
            return f"Recording stopped after ~{duration}s but the output file was not found at: {recording.output_path}"

        stats = output_path.stat()
        file_size_mb = stats.st_size / (1024 * 1024)
        duration = int((asyncio.get_event_loop().time() - recording.started_at))

        return f"Recording stopped. File: {recording.output_path} ({file_size_mb:.2f} MB, ~{duration}s)"

    # =====================================
    # BrowserStack Tools (if configured)
    # =====================================

    if bs_credentials and bs_client:

        @mcp.tool()
        async def browserstack_list_devices() -> str:
            """List all available devices on BrowserStack for remote testing.

            Returns device names, OS versions, and device IDs for starting sessions.
            """
            devices = await bs_client.get_available_devices()
            ios_count = sum(1 for d in devices if d.os == "ios")
            android_count = sum(1 for d in devices if d.os == "android")

            result = {
                "message": f"Found {len(devices)} BrowserStack devices ({ios_count} iOS, {android_count} Android)",
                "devices": [
                    {
                        "id": d.id,
                        "device": d.device,
                        "os": d.os,
                        "os_version": d.os_version,
                        "real_mobile": d.real_mobile,
                    }
                    for d in devices[:50]  # Limit to first 50
                ],
            }

            if len(devices) > 50:
                result["note"] = f"Showing first 50 of {len(devices)} devices"

            return json.dumps(result)

        @mcp.tool()
        async def browserstack_start_session(
            device: Annotated[str, Field(description="Device name (e.g., 'iPhone 14 Pro', 'Samsung Galaxy S23')")],
            os: Annotated[Literal["ios", "android"], Field(description="Operating system")],
            os_version: Annotated[str, Field(description="OS version (e.g., '16', '13.0')")],
            app_url: Annotated[
                str | None,
                Field(description="BrowserStack app URL (bs://xxx) to install. Get this from browserstack_upload_app."),
            ] = None,
        ) -> str:
            """Start a new BrowserStack session on a remote device.

            Returns a session ID that can be used as a device ID with other mobile_* tools.
            """
            session_id = await bs_client.create_session(device, os, os_version, app_url)
            robot = BrowserStackRobot(bs_credentials, session_id, bs_client)

            device_id = device_resolver.register_browserstack_session(session_id, robot)

            result = {
                "message": "BrowserStack session started successfully",
                "device_id": device_id,
                "session_id": session_id,
                "device": device,
                "os": os,
                "os_version": os_version,
                "instructions": f'Use "{device_id}" as the device parameter for mobile_* tools',
            }
            return json.dumps(result)

        @mcp.tool()
        async def browserstack_stop_session(
            session_id: Annotated[
                str,
                Field(description="Session ID from browserstack_start_session (or full device ID 'browserstack-session:xxx')"),
            ],
        ) -> str:
            """Stop an active BrowserStack session and release the device."""
            # Handle both formats
            actual_session_id = session_id.replace("browserstack-session:", "") if session_id.startswith("browserstack-session:") else session_id

            sessions = device_resolver.browserstack_sessions
            robot = sessions.get(actual_session_id)

            if not robot:
                raise ActionableError(
                    f'BrowserStack session "{actual_session_id}" not found. It may have already been stopped.'
                )

            await robot.close()
            device_resolver.unregister_browserstack_session(actual_session_id)

            return f"BrowserStack session {actual_session_id} stopped successfully. The device has been released."

        @mcp.tool()
        async def browserstack_upload_app(
            path: Annotated[str, Field(description="Local path to app file (.apk for Android, .ipa for iOS)")],
        ) -> str:
            """Upload an app file to BrowserStack for testing.

            Returns a bs:// URL that can be used to start sessions with the app.
            """
            file_path = Path(path)
            if not file_path.exists():
                raise ActionableError(f"App file not found at path: {path}")

            ext = file_path.suffix.lower()
            if ext not in (".apk", ".ipa"):
                raise ActionableError(f"Invalid app file. Must be .apk (Android) or .ipa (iOS). Got: {path}")

            app_url = await bs_client.upload_app(path)

            result = {
                "message": "App uploaded successfully to BrowserStack",
                "app_url": app_url,
                "instructions": "Use this app_url with browserstack_start_session to test your app on a device.",
            }
            return json.dumps(result)

        @mcp.tool()
        async def browserstack_list_sessions() -> str:
            """List all active BrowserStack sessions started in this server instance."""
            sessions = device_resolver.list_browserstack_sessions()

            if not sessions:
                return "No active BrowserStack sessions. Use browserstack_start_session to start one."

            result = {
                "message": f"Found {len(sessions)} active BrowserStack session(s)",
                "sessions": [
                    {
                        "session_id": s,
                        "device_id": f"browserstack-session:{s}",
                    }
                    for s in sessions
                ],
            }
            return json.dumps(result)

    return mcp
