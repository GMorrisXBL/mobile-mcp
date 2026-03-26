"""BrowserStack Robot - controls remote devices via BrowserStack's Appium hub.

Implements the Robot protocol for BrowserStack App Automate devices.
Uses WebDriver W3C Actions for touch interactions.
"""

from __future__ import annotations

from typing import Any

from ..clients.browserstack_api import (
    BrowserStackClient,
    BrowserStackCredentials,
)
from .base import (
    ActionableError,
    BaseRobot,
    InstalledApp,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)


class BrowserStackRobot(BaseRobot):
    """Robot implementation for BrowserStack cloud devices.

    Uses BrowserStack's Appium hub to control remote real devices.
    Supports both iOS and Android platforms.
    """

    def __init__(
        self,
        credentials: BrowserStackCredentials,
        session_id: str,
        client: BrowserStackClient | None = None,
    ) -> None:
        """Initialize BrowserStack robot.

        Args:
            credentials: BrowserStack authentication credentials
            session_id: Active Appium session ID
            client: Optional BrowserStack client (created if not provided)
        """
        self.credentials = credentials
        self.session_id = session_id
        self._client = client or BrowserStackClient(credentials)
        self._owns_client = client is None

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request to the BrowserStack session."""
        return await self._client.session_request(
            self.session_id, method, path, body
        )

    async def close(self) -> None:
        """Close the BrowserStack session and client."""
        try:
            await self._request("DELETE", "")
        finally:
            if self._owns_client:
                await self._client.close()

    async def get_screen_size(self) -> ScreenSize:
        """Get the screen dimensions."""
        result = await self._request("GET", "/window/rect")
        return ScreenSize(
            width=result["value"]["width"],
            height=result["value"]["height"],
            scale=1.0,  # BrowserStack returns actual pixels
        )

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        import base64

        result = await self._request("GET", "/screenshot")
        return base64.b64decode(result["value"])

    async def tap(self, x: int, y: int) -> None:
        """Tap at the specified coordinates."""
        await self._request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at the specified coordinates."""
        await self._request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 50},
                            {"type": "pointerUp", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 50},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at the specified coordinates."""
        await self._request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": duration_ms},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    async def _perform_swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: int = 1000,
    ) -> None:
        """Perform a swipe gesture."""
        await self._request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {
                                "type": "pointerMove",
                                "duration": 0,
                                "x": start_x,
                                "y": start_y,
                            },
                            {"type": "pointerDown", "button": 0},
                            {
                                "type": "pointerMove",
                                "duration": duration,
                                "x": end_x,
                                "y": end_y,
                            },
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

        # Clear actions
        await self._request("DELETE", "/actions")

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from the center of the screen."""
        screen_size = await self.get_screen_size()
        center_x = screen_size.width // 2
        center_y = screen_size.height // 2
        distance = int(screen_size.height * 0.4)

        start_x = center_x
        start_y = center_y
        end_x = center_x
        end_y = center_y

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

        await self._perform_swipe(start_x, start_y, end_x, end_y)

    async def swipe_from_coordinate(
        self,
        x: int,
        y: int,
        direction: SwipeDirection,
        distance: int | None = None,
    ) -> None:
        """Swipe from specific coordinates."""
        swipe_distance = distance or 400

        end_x = x
        end_y = y

        if direction == SwipeDirection.UP:
            end_y = y - swipe_distance
        elif direction == SwipeDirection.DOWN:
            end_y = y + swipe_distance
        elif direction == SwipeDirection.LEFT:
            end_x = x - swipe_distance
        elif direction == SwipeDirection.RIGHT:
            end_x = x + swipe_distance

        await self._perform_swipe(x, y, end_x, end_y)

    async def send_keys(self, text: str) -> None:
        """Type text into the focused element."""
        # Try to find and send keys to active element
        try:
            active_element = await self._request("POST", "/element/active")
            if active_element and active_element.get("value", {}).get("ELEMENT"):
                element_id = active_element["value"]["ELEMENT"]
                await self._request(
                    "POST",
                    f"/element/{element_id}/value",
                    {"value": list(text)},
                )
                return
        except Exception:
            pass

        # Fallback: use keyboard actions
        key_actions = []
        for char in text:
            key_actions.append({"type": "keyDown", "value": char})
            key_actions.append({"type": "keyUp", "value": char})

        await self._request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "key",
                        "id": "keyboard",
                        "actions": key_actions,
                    }
                ]
            },
        )

    async def press_button(self, button: str) -> None:
        """Press a hardware or software button."""
        button_map = {
            "HOME": "home",
            "BACK": "back",
            "VOLUME_UP": "volumeup",
            "VOLUME_DOWN": "volumedown",
            "ENTER": "\n",
        }

        if button == "ENTER":
            await self.send_keys("\n")
            return

        mapped_button = button_map.get(button)
        if not mapped_button:
            raise ActionableError(f'Button "{button}" is not supported on BrowserStack')

        # Try iOS-style button press first
        try:
            await self._request(
                "POST",
                "/appium/device/press_button",
                {"name": mapped_button},
            )
            return
        except Exception:
            pass

        # Fallback for Android: use key codes
        key_code_map = {
            "home": 3,
            "back": 4,
            "volumeup": 24,
            "volumedown": 25,
        }
        key_code = key_code_map.get(mapped_button)
        if key_code:
            await self._request(
                "POST",
                "/appium/device/press_keycode",
                {"keycode": key_code},
            )

    async def list_apps(self) -> list[InstalledApp]:
        """List installed applications.

        Note: BrowserStack doesn't provide an API to list installed apps.
        Returns an empty list - user should know which apps they've uploaded.
        """
        return []

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an application by package/bundle ID."""
        await self._request(
            "POST",
            "/appium/device/activate_app",
            {
                "bundleId": package_name,  # iOS
                "appPackage": package_name,  # Android - Appium handles both
            },
        )

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running application."""
        await self._request(
            "POST",
            "/appium/device/terminate_app",
            {
                "bundleId": package_name,
                "appPackage": package_name,
            },
        )

    async def install_app(self, path: str) -> None:
        """Install an application.

        Note: For BrowserStack, apps must be uploaded first via the API.
        The path should be a bs:// URL from a previous upload.
        """
        if path.startswith("bs://"):
            await self._request(
                "POST",
                "/appium/device/install_app",
                {"appPath": path},
            )
        else:
            raise ActionableError(
                "BrowserStack requires apps to be uploaded first. "
                "Use the BrowserStack API to upload your app and get a bs:// URL."
            )

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an application."""
        await self._request(
            "POST",
            "/appium/device/remove_app",
            {
                "bundleId": bundle_id,
                "appPackage": bundle_id,
            },
        )

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        await self._request("POST", "/url", {"url": url})

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get all UI elements currently visible on screen."""
        elements: list[ScreenElement] = []

        try:
            # Find interactive elements using XPath
            all_elements = await self._request(
                "POST",
                "/elements",
                {
                    "using": "xpath",
                    "value": (
                        "//*[@clickable='true' or "
                        "@type='XCUIElementTypeButton' or "
                        "@type='XCUIElementTypeTextField' or "
                        "@type='XCUIElementTypeStaticText']"
                    ),
                },
            )

            if all_elements and all_elements.get("value"):
                for elem in all_elements["value"]:
                    element_id = elem.get("ELEMENT") or elem.get(
                        "element-6066-11e4-a52e-4f735466cecf"
                    )
                    if not element_id:
                        continue

                    try:
                        # Get element properties
                        rect = await self._request(
                            "GET", f"/element/{element_id}/rect"
                        )

                        # Try to get text and label
                        try:
                            text_result = await self._request(
                                "GET", f"/element/{element_id}/text"
                            )
                            text = text_result.get("value", "")
                        except Exception:
                            text = ""

                        try:
                            label_result = await self._request(
                                "GET", f"/element/{element_id}/attribute/label"
                            )
                            label = label_result.get("value", "")
                        except Exception:
                            label = ""

                        elements.append(
                            ScreenElement(
                                type="element",
                                text=text or None,
                                label=label or None,
                                rect=Rect(
                                    x=rect["value"]["x"],
                                    y=rect["value"]["y"],
                                    width=rect["value"]["width"],
                                    height=rect["value"]["height"],
                                ),
                            )
                        )
                    except Exception:
                        # Skip elements that can't be inspected
                        continue

        except Exception:
            # Return empty array if element inspection fails
            pass

        return elements

    async def get_orientation(self) -> Orientation:
        """Get the current screen orientation."""
        result = await self._request("GET", "/orientation")
        orientation_str = result["value"].lower()
        return Orientation(orientation_str)

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set the screen orientation."""
        await self._request(
            "POST",
            "/orientation",
            {"orientation": orientation.value.upper()},
        )
