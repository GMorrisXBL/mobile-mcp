"""Android robot implementation using ADB."""

import asyncio
import base64
import re
from typing import Optional

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
from mobile_mcp.utils.subprocess_utils import get_adb_path, run_command, run_command_raw
from mobile_mcp.utils.xml_parser import clean_xml_content, parse_android_ui_hierarchy


# Button to Android keycode mapping
BUTTON_MAP = {
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "ENTER": "KEYCODE_ENTER",
    "DPAD_CENTER": "KEYCODE_DPAD_CENTER",
    "DPAD_UP": "KEYCODE_DPAD_UP",
    "DPAD_DOWN": "KEYCODE_DPAD_DOWN",
    "DPAD_LEFT": "KEYCODE_DPAD_LEFT",
    "DPAD_RIGHT": "KEYCODE_DPAD_RIGHT",
}


class AndroidRobot(BaseRobot):
    """Robot implementation for Android devices using ADB."""

    def __init__(self, device_id: str):
        """Initialize Android robot.

        Args:
            device_id: ADB device identifier.
        """
        self.device_id = device_id
        self._adb_path: Optional[str] = None

    @property
    def adb_path(self) -> str:
        """Get cached ADB path."""
        if self._adb_path is None:
            self._adb_path = get_adb_path()
        return self._adb_path

    async def _adb(self, *args: str, timeout: float = 30.0) -> str:
        """Run an ADB command and return stdout.

        Args:
            *args: ADB command arguments.
            timeout: Command timeout in seconds.

        Returns:
            Command stdout.
        """
        stdout, _ = await run_command(
            self.adb_path, "-s", self.device_id, *args,
            timeout=timeout,
        )
        return stdout

    async def _adb_raw(self, *args: str, timeout: float = 30.0) -> bytes:
        """Run an ADB command and return raw stdout bytes.

        Args:
            *args: ADB command arguments.
            timeout: Command timeout in seconds.

        Returns:
            Raw stdout bytes.
        """
        return await run_command_raw(
            self.adb_path, "-s", self.device_id, *args,
            timeout=timeout,
        )

    async def _adb_silent(self, *args: str, timeout: float = 30.0) -> str:
        """Run an ADB command, ignoring errors.

        Args:
            *args: ADB command arguments.
            timeout: Command timeout in seconds.

        Returns:
            Command stdout or empty string on error.
        """
        try:
            stdout, _ = await run_command(
                self.adb_path, "-s", self.device_id, *args,
                timeout=timeout,
                check=False,
            )
            return stdout
        except Exception:
            return ""

    async def get_screen_size(self) -> ScreenSize:
        """Get screen dimensions."""
        output = await self._adb("shell", "wm", "size")
        # Output format: "Physical size: 1080x1920"
        parts = output.strip().split()
        if not parts:
            raise ActionableError("Failed to get screen size")

        size_str = parts[-1]  # "1080x1920"
        width, height = map(int, size_str.split("x"))
        return ScreenSize(width=width, height=height, scale=1.0)

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        # Check display count for multi-display devices
        display_count = await self._get_display_count()

        if display_count <= 1:
            return await self._adb_raw("exec-out", "screencap", "-p")

        # Find first active display
        display_id = await self._get_first_display_id()
        if display_id:
            return await self._adb_raw("exec-out", "screencap", "-p", "-d", display_id)

        # Fallback
        return await self._adb_raw("exec-out", "screencap", "-p")

    async def _get_display_count(self) -> int:
        """Get number of displays."""
        try:
            output = await self._adb("shell", "dumpsys", "SurfaceFlinger", "--display-id")
            return len([line for line in output.split("\n") if line.startswith("Display ")])
        except Exception:
            return 1

    async def _get_first_display_id(self) -> Optional[str]:
        """Get the first active display ID."""
        try:
            output = await self._adb("shell", "cmd", "display", "get-displays")
            for line in output.split("\n"):
                if "Display id " in line and ", state ON," in line and ", uniqueId " in line:
                    match = re.search(r'uniqueId "([^"]+)"', line)
                    if match:
                        display_id = match.group(1)
                        if display_id.startswith("local:"):
                            display_id = display_id[6:]
                        return display_id
        except Exception:
            pass
        return None

    async def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        await self._adb("shell", "input", "tap", str(x), str(y))

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at coordinates."""
        await self.tap(x, y)
        await asyncio.sleep(0.1)  # Short delay between taps
        await self.tap(x, y)

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at coordinates."""
        # A long press is a swipe with no movement
        await self._adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from center of screen."""
        screen_size = await self.get_screen_size()
        center_x = screen_size.width // 2
        center_y = screen_size.height // 2

        if direction == SwipeDirection.UP:
            x0 = x1 = center_x
            y0 = int(screen_size.height * 0.80)
            y1 = int(screen_size.height * 0.20)
        elif direction == SwipeDirection.DOWN:
            x0 = x1 = center_x
            y0 = int(screen_size.height * 0.20)
            y1 = int(screen_size.height * 0.80)
        elif direction == SwipeDirection.LEFT:
            x0 = int(screen_size.width * 0.80)
            x1 = int(screen_size.width * 0.20)
            y0 = y1 = center_y
        elif direction == SwipeDirection.RIGHT:
            x0 = int(screen_size.width * 0.20)
            x1 = int(screen_size.width * 0.80)
            y0 = y1 = center_y
        else:
            raise ActionableError(f'Swipe direction "{direction}" is not supported')

        await self._adb("shell", "input", "swipe", str(x0), str(y0), str(x1), str(y1), "1000")

    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int | None = None
    ) -> None:
        """Swipe from specific coordinates."""
        screen_size = await self.get_screen_size()

        # Default to 30% of screen dimension
        default_distance_y = int(screen_size.height * 0.3)
        default_distance_x = int(screen_size.width * 0.3)
        swipe_distance_y = distance or default_distance_y
        swipe_distance_x = distance or default_distance_x

        x0, y0 = x, y

        if direction == SwipeDirection.UP:
            x1 = x
            y1 = max(0, y - swipe_distance_y)
        elif direction == SwipeDirection.DOWN:
            x1 = x
            y1 = min(screen_size.height, y + swipe_distance_y)
        elif direction == SwipeDirection.LEFT:
            x1 = max(0, x - swipe_distance_x)
            y1 = y
        elif direction == SwipeDirection.RIGHT:
            x1 = min(screen_size.width, x + swipe_distance_x)
            y1 = y
        else:
            raise ActionableError(f'Swipe direction "{direction}" is not supported')

        await self._adb("shell", "input", "swipe", str(x0), str(y0), str(x1), str(y1), "1000")

    def _escape_shell_text(self, text: str) -> str:
        """Escape text for ADB shell input."""
        return re.sub(r"([\\'\"`\s|&;()<>{}[\]$*?])", r"\\\1", text)

    def _is_ascii(self, text: str) -> bool:
        """Check if text is ASCII-only."""
        try:
            text.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    async def _is_devicekit_installed(self) -> bool:
        """Check if DeviceKit helper app is installed."""
        output = await self._adb("shell", "pm", "list", "packages")
        return "com.mobilenext.devicekit" in output

    async def send_keys(self, text: str) -> None:
        """Type text into focused element."""
        if not text:
            return

        if self._is_ascii(text):
            escaped = self._escape_shell_text(text)
            await self._adb("shell", "input", "text", escaped)
        elif await self._is_devicekit_installed():
            # Use clipboard via DeviceKit for non-ASCII
            text_b64 = base64.b64encode(text.encode()).decode()
            await self._adb(
                "shell", "am", "broadcast",
                "-a", "devicekit.clipboard.set",
                "-e", "encoding", "base64",
                "-e", "text", text_b64,
                "-n", "com.mobilenext.devicekit/.ClipboardBroadcastReceiver"
            )
            await self._adb("shell", "input", "keyevent", "KEYCODE_PASTE")
            await self._adb(
                "shell", "am", "broadcast",
                "-a", "devicekit.clipboard.clear",
                "-n", "com.mobilenext.devicekit/.ClipboardBroadcastReceiver"
            )
        else:
            raise ActionableError(
                "Non-ASCII text is not supported on Android without DeviceKit. "
                "Please install: https://github.com/mobile-next/devicekit-android"
            )

    async def press_button(self, button: str) -> None:
        """Press a hardware button."""
        keycode = BUTTON_MAP.get(button)
        if not keycode:
            raise ActionableError(f'Button "{button}" is not supported on Android')
        await self._adb("shell", "input", "keyevent", keycode)

    async def list_apps(self) -> list[InstalledApp]:
        """List installed apps with launcher activities."""
        output = await self._adb(
            "shell", "cmd", "package", "query-activities",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER"
        )

        packages = set()
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("packageName="):
                packages.add(line[12:])

        return [InstalledApp(app_name=pkg, package_name=pkg) for pkg in sorted(packages)]

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an app by package name."""
        if locale:
            # Set app locale (Android 13+)
            await self._adb_silent(
                "shell", "cmd", "locale", "set-app-locales",
                package_name, "--locales", locale
            )

        try:
            await self._adb(
                "shell", "monkey",
                "-p", package_name,
                "-c", "android.intent.category.LAUNCHER",
                "1"
            )
        except ActionableError:
            raise ActionableError(
                f'Failed to launch app "{package_name}". Please ensure it exists.'
            )

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running app."""
        await self._adb("shell", "am", "force-stop", package_name)

    async def install_app(self, path: str) -> None:
        """Install an APK."""
        try:
            await self._adb("install", "-r", path)
        except ActionableError as e:
            raise ActionableError(f"Failed to install app: {e}")

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an app."""
        try:
            await self._adb("uninstall", bundle_id)
        except ActionableError as e:
            raise ActionableError(f"Failed to uninstall app: {e}")

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        escaped_url = self._escape_shell_text(url)
        await self._adb(
            "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", escaped_url
        )

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get UI elements from screen."""
        xml_content = await self._get_ui_automator_dump()
        return parse_android_ui_hierarchy(xml_content)

    async def _get_ui_automator_dump(self) -> str:
        """Get UIAutomator XML dump with retries."""
        for attempt in range(10):
            try:
                output = await self._adb("exec-out", "uiautomator", "dump", "/dev/tty")
                if "null root node returned by UiTestAutomationBridge" in output:
                    trace(f"UIAutomator dump attempt {attempt + 1} returned null root")
                    await asyncio.sleep(0.5)
                    continue

                # Extract XML from output
                xml_start = output.find("<?xml")
                if xml_start >= 0:
                    return clean_xml_content(output[xml_start:])
            except Exception as e:
                trace(f"UIAutomator dump attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5)

        raise ActionableError("Failed to get UIAutomator XML after 10 attempts")

    async def get_orientation(self) -> Orientation:
        """Get current screen orientation."""
        output = await self._adb("shell", "settings", "get", "system", "user_rotation")
        rotation = output.strip()
        return Orientation.PORTRAIT if rotation == "0" else Orientation.LANDSCAPE

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set screen orientation."""
        value = "0" if orientation == Orientation.PORTRAIT else "1"

        # Disable auto-rotation
        await self._adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")

        # Set rotation
        await self._adb(
            "shell", "content", "insert",
            "--uri", "content://settings/system",
            "--bind", "name:s:user_rotation",
            "--bind", f"value:i:{value}"
        )

    async def get_logs(
        self, filter_text: str | None = None, lines: int = 100, level: str | None = None
    ) -> str:
        """Get device logs (logcat)."""
        args = ["logcat", "-d", "-t", str(lines)]

        if level and level != "V":
            args.append(f"*:{level}")

        output = await self._adb("shell", *args)

        if filter_text:
            # Try to get PID for the package
            try:
                pid_output = await self._adb("shell", "pidof", filter_text)
                pids = pid_output.strip().split()
                if pids:
                    lines_list = output.split("\n")
                    filtered = [line for line in lines_list if any(f" {pid} " in line for pid in pids)]
                    return "\n".join(filtered)
            except Exception:
                pass

        return output

    async def clear_logs(self) -> None:
        """Clear the logcat buffer."""
        await self._adb("logcat", "-c")
