"""Tests for mobile_mcp.robots.base module."""

import pytest

from mobile_mcp.robots.base import (
    ActionableError,
    Button,
    InstalledApp,
    Orientation,
    Rect,
    Robot,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)


class TestSwipeDirection:
    """Tests for SwipeDirection enum."""

    def test_values(self):
        """Test SwipeDirection has correct values."""
        assert SwipeDirection.UP.value == "up"
        assert SwipeDirection.DOWN.value == "down"
        assert SwipeDirection.LEFT.value == "left"
        assert SwipeDirection.RIGHT.value == "right"

    def test_from_string(self):
        """Test creating SwipeDirection from string."""
        assert SwipeDirection("up") == SwipeDirection.UP
        assert SwipeDirection("down") == SwipeDirection.DOWN
        assert SwipeDirection("left") == SwipeDirection.LEFT
        assert SwipeDirection("right") == SwipeDirection.RIGHT


class TestOrientation:
    """Tests for Orientation enum."""

    def test_values(self):
        """Test Orientation has correct values."""
        assert Orientation.PORTRAIT.value == "portrait"
        assert Orientation.LANDSCAPE.value == "landscape"

    def test_from_string(self):
        """Test creating Orientation from string."""
        assert Orientation("portrait") == Orientation.PORTRAIT
        assert Orientation("landscape") == Orientation.LANDSCAPE


class TestButton:
    """Tests for Button enum."""

    def test_common_buttons(self):
        """Test common button values."""
        assert Button.BACK.value == "BACK"
        assert Button.HOME.value == "HOME"
        assert Button.VOLUME_UP.value == "VOLUME_UP"
        assert Button.VOLUME_DOWN.value == "VOLUME_DOWN"
        assert Button.ENTER.value == "ENTER"

    def test_dpad_buttons(self):
        """Test D-pad button values for Android TV."""
        assert Button.DPAD_CENTER.value == "DPAD_CENTER"
        assert Button.DPAD_UP.value == "DPAD_UP"
        assert Button.DPAD_DOWN.value == "DPAD_DOWN"
        assert Button.DPAD_LEFT.value == "DPAD_LEFT"
        assert Button.DPAD_RIGHT.value == "DPAD_RIGHT"


class TestScreenSize:
    """Tests for ScreenSize dataclass."""

    def test_creation(self):
        """Test creating ScreenSize."""
        size = ScreenSize(width=1170, height=2532, scale=3.0)
        assert size.width == 1170
        assert size.height == 2532
        assert size.scale == 3.0

    def test_default_scale(self):
        """Test default scale value."""
        size = ScreenSize(width=1080, height=1920)
        assert size.scale == 1.0

    def test_equality(self):
        """Test ScreenSize equality."""
        size1 = ScreenSize(width=100, height=200, scale=2.0)
        size2 = ScreenSize(width=100, height=200, scale=2.0)
        assert size1 == size2


class TestRect:
    """Tests for Rect dataclass."""

    def test_creation(self):
        """Test creating Rect."""
        rect = Rect(x=10, y=20, width=100, height=50)
        assert rect.x == 10
        assert rect.y == 20
        assert rect.width == 100
        assert rect.height == 50

    def test_equality(self):
        """Test Rect equality."""
        rect1 = Rect(x=10, y=20, width=100, height=50)
        rect2 = Rect(x=10, y=20, width=100, height=50)
        assert rect1 == rect2


class TestScreenElement:
    """Tests for ScreenElement dataclass."""

    def test_creation_minimal(self):
        """Test creating ScreenElement with minimal fields."""
        element = ScreenElement(
            type="Button",
            rect=Rect(x=0, y=0, width=100, height=50),
        )
        assert element.type == "Button"
        assert element.text is None
        assert element.label is None
        assert element.focused is False

    def test_creation_full(self):
        """Test creating ScreenElement with all fields."""
        element = ScreenElement(
            type="TextField",
            rect=Rect(x=10, y=20, width=200, height=40),
            text="Hello",
            label="Input Field",
            name="email_input",
            value="test@example.com",
            identifier="email-field",
            focused=True,
        )
        assert element.type == "TextField"
        assert element.text == "Hello"
        assert element.label == "Input Field"
        assert element.name == "email_input"
        assert element.value == "test@example.com"
        assert element.identifier == "email-field"
        assert element.focused is True

    def test_to_dict_minimal(self):
        """Test to_dict with minimal fields."""
        element = ScreenElement(
            type="Button",
            rect=Rect(x=0, y=0, width=100, height=50),
        )
        result = element.to_dict()
        
        assert result["type"] == "Button"
        assert result["coordinates"] == {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 50,
        }
        assert "text" not in result
        assert "label" not in result
        assert "focused" not in result

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        element = ScreenElement(
            type="TextField",
            rect=Rect(x=10, y=20, width=200, height=40),
            text="Hello",
            label="Input",
            name="field",
            value="val",
            identifier="id",
            focused=True,
        )
        result = element.to_dict()
        
        assert result["text"] == "Hello"
        assert result["label"] == "Input"
        assert result["name"] == "field"
        assert result["value"] == "val"
        assert result["identifier"] == "id"
        assert result["focused"] is True


class TestInstalledApp:
    """Tests for InstalledApp dataclass."""

    def test_creation(self):
        """Test creating InstalledApp."""
        app = InstalledApp(
            app_name="Test App",
            package_name="com.example.test",
        )
        assert app.app_name == "Test App"
        assert app.package_name == "com.example.test"


class TestActionableError:
    """Tests for ActionableError exception."""

    def test_raise_and_catch(self):
        """Test raising and catching ActionableError."""
        with pytest.raises(ActionableError) as exc_info:
            raise ActionableError("Device not found")
        
        assert str(exc_info.value) == "Device not found"

    def test_inheritance(self):
        """Test ActionableError is an Exception."""
        error = ActionableError("Test error")
        assert isinstance(error, Exception)

    def test_message_preserved(self):
        """Test error message is preserved."""
        error = ActionableError("Custom message with details: xyz")
        assert error.args[0] == "Custom message with details: xyz"


class TestRobotProtocol:
    """Tests for Robot protocol."""

    def test_protocol_methods(self):
        """Test Robot protocol has required methods."""
        # Check that Robot is a Protocol with expected methods
        assert hasattr(Robot, "get_screen_size")
        assert hasattr(Robot, "get_screenshot")
        assert hasattr(Robot, "tap")
        assert hasattr(Robot, "double_tap")
        assert hasattr(Robot, "long_press")
        assert hasattr(Robot, "swipe")
        assert hasattr(Robot, "swipe_from_coordinate")
        assert hasattr(Robot, "send_keys")
        assert hasattr(Robot, "press_button")
        assert hasattr(Robot, "list_apps")
        assert hasattr(Robot, "launch_app")
        assert hasattr(Robot, "terminate_app")
        assert hasattr(Robot, "install_app")
        assert hasattr(Robot, "uninstall_app")
        assert hasattr(Robot, "open_url")
        assert hasattr(Robot, "get_elements_on_screen")
        assert hasattr(Robot, "get_orientation")
        assert hasattr(Robot, "set_orientation")
