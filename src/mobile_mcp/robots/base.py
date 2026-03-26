"""Robot protocol and base types for mobile automation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class SwipeDirection(str, Enum):
    """Direction for swipe gestures."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class Orientation(str, Enum):
    """Device screen orientation."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class Button(str, Enum):
    """Hardware/software buttons that can be pressed."""

    BACK = "BACK"  # Android only
    HOME = "HOME"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    ENTER = "ENTER"
    DPAD_CENTER = "DPAD_CENTER"  # Android TV
    DPAD_UP = "DPAD_UP"  # Android TV
    DPAD_DOWN = "DPAD_DOWN"  # Android TV
    DPAD_LEFT = "DPAD_LEFT"  # Android TV
    DPAD_RIGHT = "DPAD_RIGHT"  # Android TV


@dataclass
class ScreenSize:
    """Screen dimensions and scale factor."""

    width: int
    height: int
    scale: float = 1.0


@dataclass
class Rect:
    """Rectangle coordinates."""

    x: int
    y: int
    width: int
    height: int


@dataclass
class ScreenElement:
    """UI element on screen with its properties and coordinates."""

    type: str
    rect: Rect
    text: str | None = None
    label: str | None = None
    name: str | None = None
    value: str | None = None
    identifier: str | None = None
    focused: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result: dict = {
            "type": self.type,
            "coordinates": {
                "x": self.rect.x,
                "y": self.rect.y,
                "width": self.rect.width,
                "height": self.rect.height,
            },
        }
        if self.text:
            result["text"] = self.text
        if self.label:
            result["label"] = self.label
        if self.name:
            result["name"] = self.name
        if self.value:
            result["value"] = self.value
        if self.identifier:
            result["identifier"] = self.identifier
        if self.focused:
            result["focused"] = True
        return result


@dataclass
class InstalledApp:
    """Installed application information."""

    app_name: str
    package_name: str


class ActionableError(Exception):
    """User-actionable error that should be displayed without stack trace."""

    pass


@runtime_checkable
class Robot(Protocol):
    """Protocol defining the interface for mobile device automation.

    All robot implementations (Android, iOS, BrowserStack, etc.) must
    implement this protocol to provide consistent automation capabilities.
    """

    async def get_screen_size(self) -> ScreenSize:
        """Get the screen dimensions in pixels."""
        ...

    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        ...

    async def tap(self, x: int, y: int) -> None:
        """Tap at the specified coordinates."""
        ...

    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at the specified coordinates."""
        ...

    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at the specified coordinates for given duration."""
        ...

    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from the center of the screen in the specified direction."""
        ...

    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int | None = None
    ) -> None:
        """Swipe from specific coordinates in the specified direction."""
        ...

    async def send_keys(self, text: str) -> None:
        """Type text into the focused element."""
        ...

    async def press_button(self, button: str) -> None:
        """Press a hardware or software button."""
        ...

    async def list_apps(self) -> list[InstalledApp]:
        """List all installed applications."""
        ...

    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an application by package name."""
        ...

    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running application."""
        ...

    async def install_app(self, path: str) -> None:
        """Install an application from the specified path."""
        ...

    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an application by bundle ID."""
        ...

    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        ...

    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get all UI elements currently visible on screen."""
        ...

    async def get_orientation(self) -> Orientation:
        """Get the current screen orientation."""
        ...

    async def set_orientation(self, orientation: Orientation) -> None:
        """Set the screen orientation."""
        ...


class RobotWithLogs(Robot, Protocol):
    """Extended robot protocol with log support."""

    async def get_logs(
        self, filter_text: str | None = None, lines: int = 100, level: str | None = None
    ) -> str:
        """Get device logs, optionally filtered."""
        ...

    async def clear_logs(self) -> None:
        """Clear the device log buffer."""
        ...


class BaseRobot(ABC):
    """Abstract base class for robot implementations.

    Provides common functionality and enforces the Robot protocol.
    """

    @abstractmethod
    async def get_screen_size(self) -> ScreenSize:
        """Get the screen dimensions in pixels."""
        pass

    @abstractmethod
    async def get_screenshot(self) -> bytes:
        """Capture a screenshot as PNG bytes."""
        pass

    @abstractmethod
    async def tap(self, x: int, y: int) -> None:
        """Tap at the specified coordinates."""
        pass

    @abstractmethod
    async def double_tap(self, x: int, y: int) -> None:
        """Double-tap at the specified coordinates."""
        pass

    @abstractmethod
    async def long_press(self, x: int, y: int, duration_ms: int) -> None:
        """Long press at the specified coordinates for given duration."""
        pass

    @abstractmethod
    async def swipe(self, direction: SwipeDirection) -> None:
        """Swipe from the center of the screen in the specified direction."""
        pass

    @abstractmethod
    async def swipe_from_coordinate(
        self, x: int, y: int, direction: SwipeDirection, distance: int | None = None
    ) -> None:
        """Swipe from specific coordinates in the specified direction."""
        pass

    @abstractmethod
    async def send_keys(self, text: str) -> None:
        """Type text into the focused element."""
        pass

    @abstractmethod
    async def press_button(self, button: str) -> None:
        """Press a hardware or software button."""
        pass

    @abstractmethod
    async def list_apps(self) -> list[InstalledApp]:
        """List all installed applications."""
        pass

    @abstractmethod
    async def launch_app(self, package_name: str, locale: str | None = None) -> None:
        """Launch an application by package name."""
        pass

    @abstractmethod
    async def terminate_app(self, package_name: str) -> None:
        """Terminate a running application."""
        pass

    @abstractmethod
    async def install_app(self, path: str) -> None:
        """Install an application from the specified path."""
        pass

    @abstractmethod
    async def uninstall_app(self, bundle_id: str) -> None:
        """Uninstall an application by bundle ID."""
        pass

    @abstractmethod
    async def open_url(self, url: str) -> None:
        """Open a URL or deep link."""
        pass

    @abstractmethod
    async def get_elements_on_screen(self) -> list[ScreenElement]:
        """Get all UI elements currently visible on screen."""
        pass

    @abstractmethod
    async def get_orientation(self) -> Orientation:
        """Get the current screen orientation."""
        pass

    @abstractmethod
    async def set_orientation(self, orientation: Orientation) -> None:
        """Set the screen orientation."""
        pass
