"""WebDriverAgent HTTP client for iOS automation."""

import base64
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import httpx

from mobile_mcp.logger import trace
from mobile_mcp.robots.base import (
    ActionableError,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)


class WebDriverAgent:
    """HTTP client for WebDriverAgent running on iOS devices."""

    def __init__(self, host: str, port: int, timeout: float = 30.0):
        """Initialize WDA client.

        Args:
            host: WDA host (e.g., "localhost").
            port: WDA port (e.g., 8100).
            timeout: HTTP request timeout in seconds.
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def is_running(self) -> bool:
        """Check if WebDriverAgent is running and ready.

        Returns:
            True if WDA is running and ready.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/status")
            if response.status_code == 200:
                data = response.json()
                return data.get("value", {}).get("ready", False) is True
            return False
        except Exception:
            return False

    async def create_session(self) -> str:
        """Create a new WDA session.

        Returns:
            Session ID.

        Raises:
            ActionableError: If session creation fails.
        """
        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/session",
            json={"capabilities": {"alwaysMatch": {"platformName": "iOS"}}},
        )

        if response.status_code != 200:
            raise ActionableError(
                f"Failed to create WebDriver session: {response.status_code} {response.text}"
            )

        data = response.json()
        session_id = data.get("value", {}).get("sessionId")
        if not session_id:
            raise ActionableError(f"Invalid session response: {data}")

        trace(f"Created WDA session: {session_id}")
        return session_id

    async def delete_session(self, session_id: str) -> None:
        """Delete a WDA session.

        Args:
            session_id: Session ID to delete.
        """
        client = await self._get_client()
        await client.delete(f"{self.base_url}/session/{session_id}")
        trace(f"Deleted WDA session: {session_id}")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[str, None]:
        """Context manager for a WDA session.

        Yields:
            Session URL (e.g., "http://localhost:8100/session/xxx").
        """
        session_id = await self.create_session()
        session_url = f"{self.base_url}/session/{session_id}"
        try:
            yield session_url
        finally:
            await self.delete_session(session_id)

    async def get_screen_size(self, session_url: Optional[str] = None) -> ScreenSize:
        """Get screen dimensions.

        Args:
            session_url: Optional session URL. If not provided, creates a temporary session.

        Returns:
            ScreenSize object.
        """
        client = await self._get_client()

        async def _get_size(url: str) -> ScreenSize:
            response = await client.get(f"{url}/wda/screen")
            data = response.json()
            value = data.get("value", {})
            screen_size = value.get("screenSize", {})
            return ScreenSize(
                width=screen_size.get("width", 0),
                height=screen_size.get("height", 0),
                scale=value.get("scale", 1.0),
            )

        if session_url:
            return await _get_size(session_url)
        else:
            async with self.session() as url:
                return await _get_size(url)

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot.

        Returns:
            PNG image data as bytes.
        """
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/screenshot")
        data = response.json()
        return base64.b64decode(data.get("value", ""))

    async def get_page_source(self) -> dict[str, Any]:
        """Get the UI hierarchy as JSON.

        Returns:
            Source tree dictionary.
        """
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/source", params={"format": "json"})
        return response.json()

    def _filter_source_elements(self, element: dict[str, Any]) -> list[ScreenElement]:
        """Recursively filter visible elements from source tree.

        Args:
            element: Source tree element dictionary.

        Returns:
            List of ScreenElement objects.
        """
        output: list[ScreenElement] = []
        accepted_types = ["TextField", "Button", "Switch", "Icon", "SearchField", "StaticText", "Image"]

        element_type = element.get("type", "")
        is_visible = element.get("isVisible") == "1"
        rect_data = element.get("rect", {})
        rect = Rect(
            x=int(rect_data.get("x", 0)),
            y=int(rect_data.get("y", 0)),
            width=int(rect_data.get("width", 0)),
            height=int(rect_data.get("height", 0)),
        )

        # Check if element is visible and in accepted types
        if element_type in accepted_types and is_visible and rect.x >= 0 and rect.y >= 0:
            label = element.get("label")
            name = element.get("name")
            identifier = element.get("rawIdentifier")

            if label or name or identifier:
                output.append(
                    ScreenElement(
                        type=element_type,
                        rect=rect,
                        label=label,
                        name=name,
                        value=element.get("value"),
                        identifier=identifier,
                    )
                )

        # Process children
        for child in element.get("children", []):
            output.extend(self._filter_source_elements(child))

        return output

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get visible UI elements.

        Returns:
            List of ScreenElement objects.
        """
        source = await self.get_page_source()
        value = source.get("value", {})
        return self._filter_source_elements(value)

    async def send_keys(self, keys: str) -> None:
        """Type text.

        Args:
            keys: Text to type.
        """
        async with self.session() as session_url:
            client = await self._get_client()
            await client.post(
                f"{session_url}/wda/keys",
                json={"value": [keys]},
            )

    async def press_button(self, button: str) -> None:
        """Press a hardware button.

        Args:
            button: Button name (HOME, VOLUME_UP, VOLUME_DOWN, ENTER).

        Raises:
            ActionableError: If button is not supported.
        """
        button_map = {
            "HOME": "home",
            "VOLUME_UP": "volumeup",
            "VOLUME_DOWN": "volumedown",
        }

        if button == "ENTER":
            await self.send_keys("\n")
            return

        if button not in button_map:
            raise ActionableError(f'Button "{button}" is not supported on iOS')

        async with self.session() as session_url:
            client = await self._get_client()
            await client.post(
                f"{session_url}/wda/pressButton",
                json={"name": button_map[button]},
            )

    async def _perform_actions(self, session_url: str, actions: list[dict[str, Any]]) -> None:
        """Perform W3C Actions.

        Args:
            session_url: Session URL.
            actions: List of action sequences.
        """
        client = await self._get_client()
        response = await client.post(
            f"{session_url}/actions",
            json={"actions": actions},
        )

        if response.status_code != 200:
            raise ActionableError(f"WebDriver actions failed: {response.status_code} {response.text}")

        # Clear actions to ensure they complete
        await client.delete(f"{session_url}/actions")

    async def tap(self, x: int, y: int) -> None:
        """Tap at coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        async with self.session() as session_url:
            await self._perform_actions(
                session_url,
                [
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
                ],
            )

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        async with self.session() as session_url:
            await self._perform_actions(
                session_url,
                [
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
                ],
            )

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            duration_ms: Press duration in milliseconds.
        """
        async with self.session() as session_url:
            await self._perform_actions(
                session_url,
                [
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
                ],
            )

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from center of screen.

        Args:
            direction: Swipe direction.
        """
        async with self.session() as session_url:
            screen_size = await self.get_screen_size(session_url)

            # Use 60% of screen for swipe distance
            vertical_distance = int(screen_size.height * 0.6)
            horizontal_distance = int(screen_size.width * 0.6)
            center_x = screen_size.width // 2
            center_y = screen_size.height // 2

            if direction == SwipeDirection.UP:
                x0 = x1 = center_x
                y0 = center_y + vertical_distance // 2
                y1 = center_y - vertical_distance // 2
            elif direction == SwipeDirection.DOWN:
                x0 = x1 = center_x
                y0 = center_y - vertical_distance // 2
                y1 = center_y + vertical_distance // 2
            elif direction == SwipeDirection.LEFT:
                y0 = y1 = center_y
                x0 = center_x + horizontal_distance // 2
                x1 = center_x - horizontal_distance // 2
            elif direction == SwipeDirection.RIGHT:
                y0 = y1 = center_y
                x0 = center_x - horizontal_distance // 2
                x1 = center_x + horizontal_distance // 2
            else:
                raise ActionableError(f'Swipe direction "{direction}" is not supported')

            await self._perform_actions(
                session_url,
                [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x0, "y": y0},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pointerMove", "duration": 1000, "x": x1, "y": y1},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ],
            )

    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int = 400
    ) -> None:
        """Swipe from specific coordinates.

        Args:
            x: Start X coordinate.
            y: Start Y coordinate.
            direction: Swipe direction.
            distance: Swipe distance in pixels.
        """
        x0, y0 = x, y
        x1, y1 = x, y

        if direction == SwipeDirection.UP:
            y1 = y - distance
        elif direction == SwipeDirection.DOWN:
            y1 = y + distance
        elif direction == SwipeDirection.LEFT:
            x1 = x - distance
        elif direction == SwipeDirection.RIGHT:
            x1 = x + distance
        else:
            raise ActionableError(f'Swipe direction "{direction}" is not supported')

        async with self.session() as session_url:
            await self._perform_actions(
                session_url,
                [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x0, "y": y0},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pointerMove", "duration": 1000, "x": x1, "y": y1},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ],
            )

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link.

        Args:
            url: URL to open.
        """
        async with self.session() as session_url:
            client = await self._get_client()
            await client.post(f"{session_url}/url", json={"url": url})

    async def get_orientation(self) -> Orientation:
        """Get current screen orientation.

        Returns:
            Orientation enum value.
        """
        async with self.session() as session_url:
            client = await self._get_client()
            response = await client.get(f"{session_url}/orientation")
            data = response.json()
            value = data.get("value", "PORTRAIT").lower()
            return Orientation(value)

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set screen orientation.

        Args:
            orientation: Desired orientation.
        """
        async with self.session() as session_url:
            client = await self._get_client()
            await client.post(
                f"{session_url}/orientation",
                json={"orientation": orientation.value.upper()},
            )
