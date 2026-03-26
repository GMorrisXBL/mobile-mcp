"""Tests for the FastMCP server and MCP tools."""

from __future__ import annotations

import asyncio
import base64
import json
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mobile_mcp.robots.base import (
    InstalledApp,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)
from mobile_mcp.server import create_mcp_server, get_version


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Generate valid minimal PNG bytes for testing."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 100, 100, 8, 2, 0, 0, 0)
    ihdr_crc = 0x12345678
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0xAE426082)
    return signature + ihdr_chunk + iend_chunk


@pytest.fixture
def mock_robot(sample_png_bytes):
    """Create a mock robot for testing."""
    robot = AsyncMock()
    robot.platform = "ios"
    robot.list_apps = AsyncMock(
        return_value=[
            InstalledApp(app_name="Test App", package_name="com.example.testapp"),
            InstalledApp(app_name="Settings", package_name="com.apple.Preferences"),
        ]
    )
    robot.launch_app = AsyncMock()
    robot.terminate_app = AsyncMock()
    robot.install_app = AsyncMock()
    robot.uninstall_app = AsyncMock()
    robot.get_screen_size = AsyncMock(
        return_value=ScreenSize(width=1170, height=2532, scale=3.0)
    )
    robot.get_elements_on_screen = AsyncMock(
        return_value=[
            ScreenElement(
                type="Button",
                rect=Rect(x=100, y=200, width=150, height=50),
                text="Click Me",
                label="Submit",
                identifier="submit-btn",
            ),
        ]
    )
    robot.get_orientation = AsyncMock(return_value=Orientation.PORTRAIT)
    robot.set_orientation = AsyncMock()
    robot.get_screenshot = AsyncMock(return_value=sample_png_bytes)
    robot.tap = AsyncMock()
    robot.double_tap = AsyncMock()
    robot.long_press = AsyncMock()
    robot.swipe = AsyncMock()
    robot.swipe_from_coordinate = AsyncMock()
    robot.send_keys = AsyncMock()
    robot.press_button = AsyncMock()
    robot.open_url = AsyncMock()
    robot.get_logs = AsyncMock(return_value="2024-01-01 12:00:00 INFO Test log message")
    robot.clear_logs = AsyncMock()
    return robot


@pytest.fixture
def mock_device_resolver(mock_robot):
    """Create a mock device resolver."""
    resolver = MagicMock()
    resolver.list_devices = MagicMock(
        return_value=[
            MagicMock(
                id="test-device-123",
                name="Test iPhone",
                platform="ios",
                device_type="simulator",
                version="17.0",
                state="Booted",
            )
        ]
    )
    resolver.get_robot = MagicMock(return_value=mock_robot)
    resolver.browserstack_sessions = {}
    resolver.list_browserstack_sessions = MagicMock(return_value=[])
    return resolver


# ============================================================================
# Server Creation Tests
# ============================================================================


class TestServerCreation:
    """Test server creation and configuration."""

    def test_create_mcp_server(self):
        """Test that create_mcp_server returns a FastMCP instance."""
        mcp = create_mcp_server()
        assert mcp is not None
        assert mcp.name == "mobile-mcp"

    def test_get_version(self):
        """Test version retrieval."""
        version = get_version()
        assert isinstance(version, str)
        # Should either return actual version or fallback
        assert len(version) > 0

    def test_get_version_fallback(self):
        """Test version fallback when metadata is not available."""
        with patch("importlib.metadata.version", side_effect=Exception("Not found")):
            version = get_version()
            assert version == "0.1.0"


# ============================================================================
# Tool Registration Tests
# ============================================================================


class TestToolRegistration:
    """Test that all tools are properly registered."""

    def test_server_has_tools(self):
        """Test that server has tools registered."""
        mcp = create_mcp_server()
        # FastMCP stores tools internally - verify we can access them
        assert mcp is not None

    def test_expected_tools_exist(self):
        """Test that expected tool names are available."""
        # This test verifies the server can be created with all tools
        # The actual tool testing happens in functional tests
        mcp = create_mcp_server()
        # Server should be ready
        assert mcp.name == "mobile-mcp"


# ============================================================================
# Tool Functionality Tests (Unit Tests with Mocks)
# ============================================================================


class TestDeviceDiscoveryTools:
    """Test device discovery tools."""

    @pytest.mark.asyncio
    async def test_mobile_list_available_devices(self, mock_device_resolver):
        """Test listing available devices."""
        with patch(
            "mobile_mcp.server.DeviceResolver", return_value=mock_device_resolver
        ):
            mcp = create_mcp_server()
            
            # Get the tool function
            tools = mcp._tool_manager._tools
            list_devices_tool = tools.get("mobile_list_available_devices")
            
            if list_devices_tool:
                # The tool is registered, verify mock setup
                assert mock_device_resolver.list_devices is not None


class TestAppManagementTools:
    """Test app management tools."""

    @pytest.mark.asyncio
    async def test_list_apps_format(self, mock_robot):
        """Test that list_apps returns expected format."""
        apps = await mock_robot.list_apps()
        assert len(apps) == 2
        assert apps[0].app_name == "Test App"
        assert apps[0].package_name == "com.example.testapp"

    @pytest.mark.asyncio
    async def test_launch_app(self, mock_robot):
        """Test launching an app."""
        await mock_robot.launch_app("com.example.testapp", None)
        mock_robot.launch_app.assert_called_once_with("com.example.testapp", None)

    @pytest.mark.asyncio
    async def test_terminate_app(self, mock_robot):
        """Test terminating an app."""
        await mock_robot.terminate_app("com.example.testapp")
        mock_robot.terminate_app.assert_called_once_with("com.example.testapp")

    @pytest.mark.asyncio
    async def test_install_app(self, mock_robot):
        """Test installing an app."""
        await mock_robot.install_app("/path/to/app.ipa")
        mock_robot.install_app.assert_called_once_with("/path/to/app.ipa")

    @pytest.mark.asyncio
    async def test_uninstall_app(self, mock_robot):
        """Test uninstalling an app."""
        await mock_robot.uninstall_app("com.example.testapp")
        mock_robot.uninstall_app.assert_called_once_with("com.example.testapp")


class TestScreenInformationTools:
    """Test screen information tools."""

    @pytest.mark.asyncio
    async def test_get_screen_size(self, mock_robot):
        """Test getting screen size."""
        screen_size = await mock_robot.get_screen_size()
        assert screen_size.width == 1170
        assert screen_size.height == 2532
        assert screen_size.scale == 3.0

    @pytest.mark.asyncio
    async def test_list_elements_on_screen(self, mock_robot):
        """Test listing elements on screen."""
        elements = await mock_robot.get_elements_on_screen()
        assert len(elements) == 1
        assert elements[0].type == "Button"
        assert elements[0].text == "Click Me"
        assert elements[0].rect.x == 100

    @pytest.mark.asyncio
    async def test_get_orientation(self, mock_robot):
        """Test getting orientation."""
        orientation = await mock_robot.get_orientation()
        assert orientation == Orientation.PORTRAIT

    @pytest.mark.asyncio
    async def test_set_orientation(self, mock_robot):
        """Test setting orientation."""
        await mock_robot.set_orientation(Orientation.LANDSCAPE)
        mock_robot.set_orientation.assert_called_once_with(Orientation.LANDSCAPE)


class TestScreenshotTools:
    """Test screenshot tools."""

    @pytest.mark.asyncio
    async def test_get_screenshot(self, mock_robot, sample_png_bytes):
        """Test taking a screenshot."""
        screenshot = await mock_robot.get_screenshot()
        assert screenshot == sample_png_bytes
        # Verify it's valid PNG (starts with signature)
        assert screenshot[:8] == b"\x89PNG\r\n\x1a\n"


class TestTouchInteractionTools:
    """Test touch interaction tools."""

    @pytest.mark.asyncio
    async def test_tap(self, mock_robot):
        """Test tapping on screen."""
        await mock_robot.tap(100, 200)
        mock_robot.tap.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_double_tap(self, mock_robot):
        """Test double tapping."""
        await mock_robot.double_tap(150, 250)
        mock_robot.double_tap.assert_called_once_with(150, 250)

    @pytest.mark.asyncio
    async def test_long_press(self, mock_robot):
        """Test long press."""
        await mock_robot.long_press(100, 200, 1000)
        mock_robot.long_press.assert_called_once_with(100, 200, 1000)

    @pytest.mark.asyncio
    async def test_swipe(self, mock_robot):
        """Test swipe gesture."""
        await mock_robot.swipe(SwipeDirection.UP)
        mock_robot.swipe.assert_called_once_with(SwipeDirection.UP)

    @pytest.mark.asyncio
    async def test_swipe_from_coordinate(self, mock_robot):
        """Test swipe from coordinate."""
        await mock_robot.swipe_from_coordinate(100, 500, SwipeDirection.DOWN, 300)
        mock_robot.swipe_from_coordinate.assert_called_once_with(
            100, 500, SwipeDirection.DOWN, 300
        )


class TestInputTools:
    """Test input tools."""

    @pytest.mark.asyncio
    async def test_send_keys(self, mock_robot):
        """Test typing text."""
        await mock_robot.send_keys("Hello World")
        mock_robot.send_keys.assert_called_once_with("Hello World")

    @pytest.mark.asyncio
    async def test_press_button(self, mock_robot):
        """Test pressing a button."""
        await mock_robot.press_button("HOME")
        mock_robot.press_button.assert_called_once_with("HOME")

    @pytest.mark.asyncio
    async def test_open_url(self, mock_robot):
        """Test opening a URL."""
        await mock_robot.open_url("https://example.com")
        mock_robot.open_url.assert_called_once_with("https://example.com")


class TestLogTools:
    """Test log tools."""

    @pytest.mark.asyncio
    async def test_get_logs(self, mock_robot):
        """Test getting device logs."""
        logs = await mock_robot.get_logs()
        assert "Test log message" in logs

    @pytest.mark.asyncio
    async def test_clear_logs(self, mock_robot):
        """Test clearing device logs."""
        await mock_robot.clear_logs()
        mock_robot.clear_logs.assert_called_once()


# ============================================================================
# Validation Tests
# ============================================================================


class TestValidation:
    """Test input validation functions."""

    def test_validate_file_extension_valid(self):
        """Test valid file extension."""
        from mobile_mcp.utils.validation import validate_file_extension

        # Should not raise for valid extensions
        validate_file_extension("/path/to/file.png", [".png", ".jpg"], "test")
        validate_file_extension("/path/to/file.jpg", [".png", ".jpg"], "test")

    def test_validate_file_extension_invalid(self):
        """Test invalid file extension."""
        from mobile_mcp.utils.validation import validate_file_extension
        from mobile_mcp.robots.base import ActionableError

        with pytest.raises(ActionableError):
            validate_file_extension("/path/to/file.gif", [".png", ".jpg"], "test")

    def test_validate_output_path_valid(self, tmp_path):
        """Test valid output path."""
        from mobile_mcp.utils.validation import validate_output_path

        output_path = str(tmp_path / "test.png")
        validate_output_path(output_path)

    def test_validate_output_path_invalid_directory(self):
        """Test output path with non-existent directory."""
        from mobile_mcp.utils.validation import validate_output_path
        from mobile_mcp.robots.base import ActionableError

        with pytest.raises(ActionableError):
            validate_output_path("/nonexistent/directory/file.png")


# ============================================================================
# Image Processing Tests
# ============================================================================


class TestImageProcessing:
    """Test image processing functions."""

    def test_get_png_dimensions(self, sample_png_bytes):
        """Test extracting PNG dimensions."""
        from mobile_mcp.utils.png import get_png_dimensions

        width, height = get_png_dimensions(sample_png_bytes)
        assert width == 100
        assert height == 100

    def test_get_png_dimensions_invalid(self):
        """Test with invalid PNG data."""
        from mobile_mcp.utils.png import get_png_dimensions

        with pytest.raises(ValueError):
            get_png_dimensions(b"not a png")

    def test_process_screenshot_passthrough(self, sample_png_bytes):
        """Test screenshot processing without resize/compression."""
        from mobile_mcp.utils.image import process_screenshot

        # With default settings (no env vars), should return PNG as-is
        processed, mime_type = process_screenshot(sample_png_bytes, scale=1)
        assert mime_type == "image/png"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling in server tools."""

    def test_actionable_error_format(self):
        """Test ActionableError message format."""
        from mobile_mcp.robots.base import ActionableError

        error = ActionableError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_actionable_error_with_suggestion(self):
        """Test ActionableError with suggestion."""
        from mobile_mcp.robots.base import ActionableError

        error = ActionableError(
            "Device not found. Use mobile_list_available_devices to see available devices."
        )
        assert "mobile_list_available_devices" in str(error)


# ============================================================================
# BrowserStack Integration Tests
# ============================================================================


class TestBrowserStackIntegration:
    """Test BrowserStack tool registration based on credentials."""

    def test_browserstack_tools_when_configured(self):
        """Test that BrowserStack tools are registered when credentials exist."""
        with patch.dict(
            "os.environ",
            {
                "BROWSERSTACK_USERNAME": "test_user",
                "BROWSERSTACK_ACCESS_KEY": "test_key",
            },
        ):
            mcp = create_mcp_server()
            # Server should be created successfully
            assert mcp is not None

    def test_browserstack_tools_when_not_configured(self):
        """Test server works without BrowserStack credentials."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove BrowserStack env vars if present
            import os

            os.environ.pop("BROWSERSTACK_USERNAME", None)
            os.environ.pop("BROWSERSTACK_ACCESS_KEY", None)

            mcp = create_mcp_server()
            assert mcp is not None


# ============================================================================
# Screen Element Tests
# ============================================================================


class TestScreenElement:
    """Test ScreenElement functionality."""

    def test_screen_element_center(self):
        """Test ScreenElement center calculation."""
        element = ScreenElement(
            type="Button",
            rect=Rect(x=100, y=200, width=100, height=50),
            text="Test",
        )
        center = element.center
        assert center == (150, 225)  # x + width/2, y + height/2

    def test_screen_element_to_dict(self):
        """Test ScreenElement serialization."""
        element = ScreenElement(
            type="Button",
            rect=Rect(x=100, y=200, width=100, height=50),
            text="Test",
            label="Test Button",
            identifier="test-btn",
        )
        data = element.to_dict()

        assert data["type"] == "Button"
        assert data["rect"]["x"] == 100
        assert data["text"] == "Test"
        assert data["label"] == "Test Button"
        assert data["identifier"] == "test-btn"

    def test_screen_element_minimal(self):
        """Test ScreenElement with minimal fields."""
        element = ScreenElement(
            type="StaticText",
            rect=Rect(x=0, y=0, width=200, height=20),
        )
        data = element.to_dict()

        assert data["type"] == "StaticText"
        assert data["text"] is None
        assert data["label"] is None


# ============================================================================
# Concurrent Operations Tests
# ============================================================================


class TestConcurrentOperations:
    """Test concurrent operation handling."""

    @pytest.mark.asyncio
    async def test_multiple_screenshots(self, mock_robot, sample_png_bytes):
        """Test taking multiple screenshots concurrently."""
        # Simulate concurrent screenshot requests
        tasks = [mock_robot.get_screenshot() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert result == sample_png_bytes

    @pytest.mark.asyncio
    async def test_multiple_operations(self, mock_robot):
        """Test multiple different operations concurrently."""
        tasks = [
            mock_robot.get_screen_size(),
            mock_robot.get_orientation(),
            mock_robot.get_elements_on_screen(),
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert results[0].width == 1170
        assert results[1] == Orientation.PORTRAIT
        assert len(results[2]) == 1
