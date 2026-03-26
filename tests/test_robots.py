"""Tests for mobile_mcp.robots implementations."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mobile_mcp.robots.base import (
    ActionableError,
    InstalledApp,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)


# ============================================================================
# Android Robot Tests
# ============================================================================


class TestAndroidRobot:
    """Tests for AndroidRobot."""

    @pytest.fixture
    def robot(self, android_device_id):
        """Create an Android robot for testing."""
        from mobile_mcp.robots.android import AndroidRobot
        return AndroidRobot(android_device_id)

    def test_init(self, robot, android_device_id):
        """Test robot initialization."""
        assert robot.device_id == android_device_id

    @pytest.mark.asyncio
    async def test_get_screen_size(self, robot):
        """Test getting screen size."""
        with patch.object(robot, "_run_adb", return_value="Physical size: 1080x2400"):
            size = await robot.get_screen_size()
            assert size.width == 1080
            assert size.height == 2400

    @pytest.mark.asyncio
    async def test_get_screenshot(self, robot, sample_png_bytes):
        """Test taking a screenshot."""
        with patch.object(robot, "_run_adb_raw", return_value=sample_png_bytes):
            screenshot = await robot.get_screenshot()
            assert screenshot == sample_png_bytes

    @pytest.mark.asyncio
    async def test_tap(self, robot):
        """Test tap action."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.tap(100, 200)
            # Verify adb was called with input tap
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_double_tap(self, robot):
        """Test double tap action."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.double_tap(100, 200)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_long_press(self, robot):
        """Test long press action."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.long_press(100, 200, 1000)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_swipe(self, robot):
        """Test swipe action."""
        with patch.object(
            robot, "get_screen_size", return_value=ScreenSize(1080, 2400, 1.0)
        ):
            with patch.object(robot, "_run_adb", return_value="") as mock:
                await robot.swipe(SwipeDirection.UP)
                mock.assert_called()

    @pytest.mark.asyncio
    async def test_swipe_from_coordinate(self, robot):
        """Test swipe from coordinate."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.swipe_from_coordinate(500, 1000, SwipeDirection.DOWN, 400)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_send_keys(self, robot):
        """Test sending keys."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.send_keys("hello")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_press_button(self, robot):
        """Test pressing button."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.press_button("HOME")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_list_apps(self, robot):
        """Test listing apps."""
        output = "packageName=com.example.app1\npackageName=com.example.app2\n"
        with patch.object(robot, "_run_adb", return_value=output):
            apps = await robot.list_apps()
            assert len(apps) == 2
            assert apps[0].package_name == "com.example.app1"

    @pytest.mark.asyncio
    async def test_launch_app(self, robot):
        """Test launching app."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.launch_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_terminate_app(self, robot):
        """Test terminating app."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.terminate_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_open_url(self, robot):
        """Test opening URL."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.open_url("https://example.com")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_get_orientation(self, robot):
        """Test getting orientation."""
        with patch.object(robot, "_run_adb", return_value="0"):
            orientation = await robot.get_orientation()
            assert orientation == Orientation.PORTRAIT

    @pytest.mark.asyncio
    async def test_set_orientation(self, robot):
        """Test setting orientation."""
        with patch.object(robot, "_run_adb", return_value="") as mock:
            await robot.set_orientation(Orientation.LANDSCAPE)
            mock.assert_called()


# ============================================================================
# iOS Robot Tests
# ============================================================================


class TestIosRobot:
    """Tests for IosRobot."""

    @pytest.fixture
    def robot(self, ios_device_id):
        """Create an iOS robot for testing."""
        from mobile_mcp.robots.ios import IosRobot
        return IosRobot(ios_device_id)

    def test_init(self, robot, ios_device_id):
        """Test robot initialization."""
        assert robot.device_id == ios_device_id

    @pytest.mark.asyncio
    async def test_get_screen_size(self, robot, sample_screen_size):
        """Test getting screen size."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.get_screen_size = AsyncMock(return_value=sample_screen_size)
            mock_get_wda.return_value = mock_wda

            size = await robot.get_screen_size()
            assert size == sample_screen_size

    @pytest.mark.asyncio
    async def test_get_screenshot(self, robot, sample_png_bytes):
        """Test taking a screenshot."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.get_screenshot = AsyncMock(return_value=sample_png_bytes)
            mock_get_wda.return_value = mock_wda

            screenshot = await robot.get_screenshot()
            assert screenshot == sample_png_bytes

    @pytest.mark.asyncio
    async def test_tap(self, robot):
        """Test tap action."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.tap = AsyncMock()
            mock_get_wda.return_value = mock_wda

            await robot.tap(100, 200)
            mock_wda.tap.assert_called_with(100, 200)

    @pytest.mark.asyncio
    async def test_swipe(self, robot):
        """Test swipe action."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.swipe = AsyncMock()
            mock_get_wda.return_value = mock_wda

            await robot.swipe(SwipeDirection.UP)
            mock_wda.swipe.assert_called()

    @pytest.mark.asyncio
    async def test_send_keys(self, robot):
        """Test sending keys."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.send_keys = AsyncMock()
            mock_get_wda.return_value = mock_wda

            await robot.send_keys("hello")
            mock_wda.send_keys.assert_called_with("hello")

    @pytest.mark.asyncio
    async def test_list_apps(self, robot):
        """Test listing apps."""
        apps_output = "com.example.app1 App1\ncom.example.app2 App2\n"
        with patch.object(robot, "_run_ios", return_value=apps_output):
            apps = await robot.list_apps()
            assert len(apps) == 2

    @pytest.mark.asyncio
    async def test_launch_app(self, robot):
        """Test launching app."""
        with patch.object(robot, "_run_ios", return_value="") as mock:
            await robot.launch_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_open_url(self, robot):
        """Test opening URL."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.open_url = AsyncMock()
            mock_get_wda.return_value = mock_wda

            await robot.open_url("https://example.com")
            mock_wda.open_url.assert_called_with("https://example.com")


# ============================================================================
# Simulator Robot Tests
# ============================================================================


class TestSimulatorRobot:
    """Tests for SimulatorRobot."""

    @pytest.fixture
    def robot(self, simulator_device_id):
        """Create a Simulator robot for testing."""
        from mobile_mcp.robots.simulator import SimulatorRobot
        return SimulatorRobot(simulator_device_id)

    def test_init(self, robot, simulator_device_id):
        """Test robot initialization."""
        assert robot.device_id == simulator_device_id

    @pytest.mark.asyncio
    async def test_get_screen_size(self, robot, sample_screen_size):
        """Test getting screen size."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.get_screen_size = AsyncMock(return_value=sample_screen_size)
            mock_get_wda.return_value = mock_wda

            size = await robot.get_screen_size()
            assert size == sample_screen_size

    @pytest.mark.asyncio
    async def test_get_screenshot(self, robot, sample_png_bytes):
        """Test taking a screenshot."""
        with patch.object(robot, "_get_wda_client") as mock_get_wda:
            mock_wda = AsyncMock()
            mock_wda.get_screenshot = AsyncMock(return_value=sample_png_bytes)
            mock_get_wda.return_value = mock_wda

            screenshot = await robot.get_screenshot()
            assert screenshot == sample_png_bytes

    @pytest.mark.asyncio
    async def test_install_app(self, robot):
        """Test installing app on simulator."""
        with patch.object(robot, "_run_simctl", return_value="") as mock:
            await robot.install_app("/path/to/app.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_uninstall_app(self, robot):
        """Test uninstalling app from simulator."""
        with patch.object(robot, "_run_simctl", return_value="") as mock:
            await robot.uninstall_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_launch_app(self, robot):
        """Test launching app on simulator."""
        with patch.object(robot, "_run_simctl", return_value="") as mock:
            await robot.launch_app("com.example.app")
            mock.assert_called()


# ============================================================================
# BrowserStack Robot Tests
# ============================================================================


class TestBrowserStackRobot:
    """Tests for BrowserStackRobot."""

    @pytest.fixture
    def robot(self, browserstack_credentials, browserstack_session_id):
        """Create a BrowserStack robot for testing."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot
        return BrowserStackRobot(browserstack_credentials, browserstack_session_id)

    def test_init(self, robot, browserstack_credentials, browserstack_session_id):
        """Test robot initialization."""
        assert robot.credentials == browserstack_credentials
        assert robot.session_id == browserstack_session_id

    @pytest.mark.asyncio
    async def test_get_screen_size(self, robot):
        """Test getting screen size."""
        with patch.object(
            robot,
            "_request",
            return_value={"value": {"width": 390, "height": 844}},
        ):
            size = await robot.get_screen_size()
            assert size.width == 390
            assert size.height == 844

    @pytest.mark.asyncio
    async def test_get_screenshot(self, robot, sample_png_bytes):
        """Test taking a screenshot."""
        encoded = base64.b64encode(sample_png_bytes).decode("ascii")
        with patch.object(robot, "_request", return_value={"value": encoded}):
            screenshot = await robot.get_screenshot()
            assert screenshot == sample_png_bytes

    @pytest.mark.asyncio
    async def test_tap(self, robot):
        """Test tap action."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.tap(100, 200)
            mock.assert_called_with("POST", "/actions", pytest.approx({"actions": pytest.approx([pytest.approx({})])}, rel=1e-9) if False else {"actions": [{"type": "pointer", "id": "finger1", "parameters": {"pointerType": "touch"}, "actions": [{"type": "pointerMove", "duration": 0, "x": 100, "y": 200}, {"type": "pointerDown", "button": 0}, {"type": "pause", "duration": 100}, {"type": "pointerUp", "button": 0}]}]})

    @pytest.mark.asyncio
    async def test_double_tap(self, robot):
        """Test double tap action."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.double_tap(100, 200)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_long_press(self, robot):
        """Test long press action."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.long_press(100, 200, 1000)
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_swipe(self, robot):
        """Test swipe action."""
        with patch.object(
            robot, "get_screen_size", return_value=ScreenSize(390, 844, 1.0)
        ):
            with patch.object(robot, "_perform_swipe", return_value=None) as mock:
                await robot.swipe(SwipeDirection.UP)
                mock.assert_called()

    @pytest.mark.asyncio
    async def test_send_keys(self, robot):
        """Test sending keys."""
        # Mock active element found
        with patch.object(
            robot,
            "_request",
            side_effect=[
                {"value": {"ELEMENT": "elem-123"}},
                None,
            ],
        ):
            await robot.send_keys("hello")

    @pytest.mark.asyncio
    async def test_send_keys_fallback(self, robot):
        """Test sending keys with fallback to keyboard actions."""
        # Mock no active element
        with patch.object(
            robot,
            "_request",
            side_effect=[
                {"value": {}},
                None,
            ],
        ):
            await robot.send_keys("hi")

    @pytest.mark.asyncio
    async def test_press_button_home(self, robot):
        """Test pressing HOME button."""
        with patch.object(robot, "_request", return_value=None):
            await robot.press_button("HOME")

    @pytest.mark.asyncio
    async def test_press_button_enter(self, robot):
        """Test pressing ENTER button."""
        with patch.object(robot, "send_keys", return_value=None) as mock:
            await robot.press_button("ENTER")
            mock.assert_called_with("\n")

    @pytest.mark.asyncio
    async def test_press_button_unsupported(self, robot):
        """Test pressing unsupported button."""
        with pytest.raises(ActionableError, match="not supported"):
            await robot.press_button("UNSUPPORTED_BUTTON")

    @pytest.mark.asyncio
    async def test_list_apps(self, robot):
        """Test listing apps (returns empty for BrowserStack)."""
        apps = await robot.list_apps()
        assert apps == []

    @pytest.mark.asyncio
    async def test_launch_app(self, robot):
        """Test launching app."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.launch_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_terminate_app(self, robot):
        """Test terminating app."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.terminate_app("com.example.app")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_install_app_bs_url(self, robot):
        """Test installing app with bs:// URL."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.install_app("bs://app123")
            mock.assert_called()

    @pytest.mark.asyncio
    async def test_install_app_local_path(self, robot):
        """Test installing app with local path (should fail)."""
        with pytest.raises(ActionableError, match="uploaded first"):
            await robot.install_app("/local/path/app.apk")

    @pytest.mark.asyncio
    async def test_open_url(self, robot):
        """Test opening URL."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.open_url("https://example.com")
            mock.assert_called_with("POST", "/url", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_get_orientation(self, robot):
        """Test getting orientation."""
        with patch.object(robot, "_request", return_value={"value": "PORTRAIT"}):
            orientation = await robot.get_orientation()
            assert orientation == Orientation.PORTRAIT

    @pytest.mark.asyncio
    async def test_set_orientation(self, robot):
        """Test setting orientation."""
        with patch.object(robot, "_request", return_value=None) as mock:
            await robot.set_orientation(Orientation.LANDSCAPE)
            mock.assert_called_with(
                "POST", "/orientation", {"orientation": "LANDSCAPE"}
            )

    @pytest.mark.asyncio
    async def test_close(self, robot):
        """Test closing session."""
        with patch.object(robot, "_request", return_value=None) as mock_request:
            with patch.object(robot._client, "close", return_value=None) as mock_close:
                await robot.close()
                mock_request.assert_called_with("DELETE", "")

    @pytest.mark.asyncio
    async def test_get_elements_on_screen(self, robot):
        """Test getting elements on screen."""
        elements_response = {
            "value": [
                {"ELEMENT": "elem-1"},
                {"ELEMENT": "elem-2"},
            ]
        }
        rect_response = {"value": {"x": 10, "y": 20, "width": 100, "height": 50}}
        text_response = {"value": "Button"}
        label_response = {"value": "Submit"}

        with patch.object(
            robot,
            "_request",
            side_effect=[
                elements_response,
                rect_response,
                text_response,
                label_response,
                rect_response,
                text_response,
                label_response,
            ],
        ):
            elements = await robot.get_elements_on_screen()
            assert len(elements) == 2
            assert elements[0].text == "Button"
            assert elements[0].label == "Submit"
