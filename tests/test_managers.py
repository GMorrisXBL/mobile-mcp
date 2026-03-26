"""Tests for mobile_mcp.managers modules."""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from mobile_mcp.managers.android_manager import (
    AndroidDevice,
    AndroidDeviceDetails,
    AndroidDeviceManager,
    get_adb_path,
)
from mobile_mcp.managers.ios_manager import (
    IosDevice,
    IosDeviceDetails,
    IosDeviceInfo,
    IosManager,
    get_go_ios_path,
)
from mobile_mcp.managers.device_resolver import (
    DeviceInfo,
    DeviceResolver,
)
from mobile_mcp.robots.base import ActionableError


# ============================================================================
# Android Manager Tests
# ============================================================================


class TestGetAdbPath:
    """Tests for get_adb_path function."""

    def test_from_android_home(self, tmp_path):
        """Test getting adb path from ANDROID_HOME."""
        adb_path = tmp_path / "platform-tools" / "adb"
        adb_path.parent.mkdir(parents=True)
        adb_path.touch()

        with patch.dict("os.environ", {"ANDROID_HOME": str(tmp_path)}):
            result = get_adb_path()
            assert str(tmp_path) in result

    def test_fallback_to_adb(self):
        """Test fallback to 'adb' when ANDROID_HOME not set."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.path.exists", return_value=False):
                result = get_adb_path()
                assert result == "adb" or "adb" in result


class TestAndroidDeviceManager:
    """Tests for AndroidDeviceManager."""

    @pytest.fixture
    def manager(self):
        """Create an Android device manager for testing."""
        return AndroidDeviceManager()

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.adb_path is not None

    def test_get_connected_devices(self, manager, mock_adb_devices_output):
        """Test getting connected devices."""
        with patch.object(manager, "_run_adb", return_value=mock_adb_devices_output):
            with patch.object(manager, "_get_device_type", return_value="mobile"):
                devices = manager.get_connected_devices()

                assert len(devices) == 2
                assert devices[0].device_id == "emulator-5554"
                assert devices[1].device_id == "192.168.1.100:5555"

    def test_get_connected_devices_empty(self, manager):
        """Test getting devices when none connected."""
        with patch.object(
            manager, "_run_adb", return_value="List of devices attached\n"
        ):
            devices = manager.get_connected_devices()
            assert len(devices) == 0

    def test_get_connected_devices_with_details(self, manager, mock_adb_devices_output):
        """Test getting devices with details."""
        with patch.object(manager, "_run_adb", return_value=mock_adb_devices_output):
            with patch.object(manager, "_get_device_type", return_value="mobile"):
                with patch.object(manager, "_get_device_version", return_value="14"):
                    with patch.object(
                        manager, "_get_device_name", return_value="Pixel 7"
                    ):
                        devices = manager.get_connected_devices_with_details()

                        assert len(devices) == 2
                        assert devices[0].version == "14"
                        assert devices[0].name == "Pixel 7"

    def test_get_device_type_mobile(self, manager):
        """Test detecting mobile device type."""
        with patch.object(
            manager,
            "_run_adb",
            return_value="feature:android.hardware.screen.portrait\n",
        ):
            device_type = manager._get_device_type("emulator-5554")
            assert device_type == "mobile"

    def test_get_device_type_tv(self, manager):
        """Test detecting TV device type."""
        with patch.object(
            manager,
            "_run_adb",
            return_value="feature:android.software.leanback\n",
        ):
            device_type = manager._get_device_type("emulator-5554")
            assert device_type == "tv"

    def test_get_device_version(self, manager):
        """Test getting device version."""
        with patch.object(manager, "_run_adb", return_value="14"):
            version = manager._get_device_version("emulator-5554")
            assert version == "14"

    def test_get_device_name_emulator(self, manager):
        """Test getting emulator name."""
        with patch.object(manager, "_run_adb", return_value="Pixel_9_Pro"):
            name = manager._get_device_name("emulator-5554")
            assert name == "Pixel 9 Pro"  # Underscores replaced

    def test_get_device_name_real_device(self, manager):
        """Test getting real device name."""
        # First call returns empty (not an emulator), second returns model
        with patch.object(
            manager, "_run_adb", side_effect=["", "Samsung Galaxy S23"]
        ):
            name = manager._get_device_name("device-123")
            assert name == "Samsung Galaxy S23"

    def test_is_adb_available_true(self, manager):
        """Test adb availability check when available."""
        with patch.object(manager, "_run_adb", return_value="Android Debug Bridge"):
            assert manager.is_adb_available() is True

    def test_is_adb_available_false(self, manager):
        """Test adb availability check when not available."""
        with patch.object(manager, "_run_adb", side_effect=Exception("Not found")):
            assert manager.is_adb_available() is False


# ============================================================================
# iOS Manager Tests
# ============================================================================


class TestGetGoIosPath:
    """Tests for get_go_ios_path function."""

    def test_from_env_var(self):
        """Test getting path from environment variable."""
        with patch.dict("os.environ", {"GO_IOS_PATH": "/custom/path/ios"}):
            result = get_go_ios_path()
            assert result == "/custom/path/ios"

    def test_fallback_to_ios(self):
        """Test fallback to 'ios' command."""
        with patch.dict("os.environ", {}, clear=True):
            result = get_go_ios_path()
            assert result == "ios"


class TestIosManager:
    """Tests for IosManager."""

    @pytest.fixture
    def manager(self):
        """Create an iOS manager for testing."""
        return IosManager()

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.ios_path is not None

    def test_is_go_ios_installed_true(self, manager):
        """Test go-ios installation check when installed."""
        with patch.object(
            manager, "_run_ios", return_value='{"version": "v1.0.0"}'
        ):
            assert manager.is_go_ios_installed() is True

    def test_is_go_ios_installed_local_build(self, manager):
        """Test go-ios installation check for local build."""
        with patch.object(
            manager, "_run_ios", return_value='{"version": "local-build"}'
        ):
            assert manager.is_go_ios_installed() is True

    def test_is_go_ios_installed_false(self, manager):
        """Test go-ios installation check when not installed."""
        with patch.object(manager, "_run_ios", side_effect=Exception("Not found")):
            assert manager.is_go_ios_installed() is False

    def test_get_device_name(self, manager, mock_go_ios_info_output):
        """Test getting device name."""
        with patch.object(manager, "_run_ios", return_value=mock_go_ios_info_output):
            name = manager.get_device_name("device-udid")
            assert name == "Test iPhone"

    def test_get_device_info(self, manager, mock_go_ios_info_output):
        """Test getting device info."""
        with patch.object(manager, "_run_ios", return_value=mock_go_ios_info_output):
            info = manager.get_device_info("device-udid")

            assert isinstance(info, IosDeviceInfo)
            assert info.device_name == "Test iPhone"
            assert info.product_version == "16.5"
            assert info.device_class == "iPhone"

    def test_list_devices(self, manager, mock_go_ios_list_output, mock_go_ios_info_output):
        """Test listing devices."""
        with patch.object(manager, "is_go_ios_installed", return_value=True):
            with patch.object(
                manager,
                "_run_ios",
                side_effect=[mock_go_ios_list_output, mock_go_ios_info_output, mock_go_ios_info_output],
            ):
                devices = manager.list_devices()

                assert len(devices) == 2
                assert devices[0].device_id == "00008030-001A35E83C38802E"

    def test_list_devices_not_installed(self, manager):
        """Test listing devices when go-ios not installed."""
        with patch.object(manager, "is_go_ios_installed", return_value=False):
            devices = manager.list_devices()
            assert len(devices) == 0

    def test_list_devices_with_details(
        self, manager, mock_go_ios_list_output, mock_go_ios_info_output
    ):
        """Test listing devices with details."""
        with patch.object(manager, "is_go_ios_installed", return_value=True):
            with patch.object(
                manager,
                "_run_ios",
                side_effect=[mock_go_ios_list_output, mock_go_ios_info_output, mock_go_ios_info_output],
            ):
                devices = manager.list_devices_with_details()

                assert len(devices) == 2
                assert devices[0].version == "16.5"


# ============================================================================
# Device Resolver Tests
# ============================================================================


class TestDeviceResolver:
    """Tests for DeviceResolver."""

    @pytest.fixture
    def resolver(self):
        """Create a device resolver for testing."""
        return DeviceResolver()

    def test_init(self, resolver):
        """Test resolver initialization."""
        assert resolver.browserstack_sessions == {}
        assert resolver._android_manager is not None
        assert resolver._ios_manager is not None

    def test_get_robot_browserstack_session(self, resolver, browserstack_credentials):
        """Test getting robot for BrowserStack session."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot

        robot = BrowserStackRobot(browserstack_credentials, "session-123")
        resolver.browserstack_sessions["session-123"] = robot

        result = resolver.get_robot("browserstack-session:session-123")
        assert result is robot

    def test_get_robot_browserstack_not_found(self, resolver):
        """Test getting robot for nonexistent BrowserStack session."""
        with pytest.raises(ActionableError, match="not found"):
            resolver.get_robot("browserstack-session:nonexistent")

    def test_get_robot_android_device(self, resolver, android_device_id):
        """Test getting robot for Android device."""
        mock_device = AndroidDevice(device_id=android_device_id, device_type="mobile")

        with patch.object(resolver._ios_manager, "list_devices", return_value=[]):
            with patch.object(
                resolver._android_manager,
                "get_connected_devices",
                return_value=[mock_device],
            ):
                robot = resolver.get_robot(android_device_id)

                from mobile_mcp.robots.android import AndroidRobot
                assert isinstance(robot, AndroidRobot)

    def test_get_robot_ios_device(self, resolver, ios_device_id):
        """Test getting robot for iOS physical device."""
        mock_device = IosDevice(device_id=ios_device_id, device_name="iPhone")

        with patch.object(
            resolver._ios_manager, "list_devices", return_value=[mock_device]
        ):
            robot = resolver.get_robot(ios_device_id)

            from mobile_mcp.robots.ios import IosRobot
            assert isinstance(robot, IosRobot)

    def test_get_robot_simulator(self, resolver, simulator_device_id):
        """Test getting robot for iOS simulator."""
        with patch.object(resolver._ios_manager, "list_devices", return_value=[]):
            with patch.object(
                resolver._android_manager, "get_connected_devices", return_value=[]
            ):
                with patch.object(resolver, "_is_simulator", return_value=True):
                    robot = resolver.get_robot(simulator_device_id)

                    from mobile_mcp.robots.simulator import SimulatorRobot
                    assert isinstance(robot, SimulatorRobot)

    def test_get_robot_not_found(self, resolver):
        """Test getting robot for nonexistent device."""
        with patch.object(resolver._ios_manager, "list_devices", return_value=[]):
            with patch.object(
                resolver._android_manager, "get_connected_devices", return_value=[]
            ):
                with patch.object(resolver, "_is_simulator", return_value=False):
                    with pytest.raises(ActionableError, match="not found"):
                        resolver.get_robot("nonexistent-device")

    def test_list_devices(self, resolver, mock_simctl_list_output):
        """Test listing all devices."""
        android_device = AndroidDeviceDetails(
            device_id="emulator-5554",
            device_type="mobile",
            version="14",
            name="Pixel 7",
        )
        ios_device = IosDeviceDetails(
            device_id="device-udid",
            device_name="iPhone",
            version="16.5",
        )

        with patch.object(
            resolver._android_manager,
            "get_connected_devices_with_details",
            return_value=[android_device],
        ):
            with patch.object(
                resolver._ios_manager,
                "list_devices_with_details",
                return_value=[ios_device],
            ):
                with patch.object(
                    resolver, "_list_simulators", return_value=[]
                ):
                    devices = resolver.list_devices()

                    assert len(devices) == 2
                    assert devices[0].platform == "android"
                    assert devices[1].platform == "ios"

    def test_list_simulators(self, resolver, mock_simctl_list_output):
        """Test listing iOS simulators."""
        from mobile_mcp.utils.subprocess_utils import CommandResult

        mock_result = CommandResult(
            returncode=0,
            stdout=mock_simctl_list_output,
            stderr=None,
        )

        with patch(
            "mobile_mcp.managers.device_resolver.run_command_sync",
            return_value=mock_result,
        ):
            simulators = resolver._list_simulators()

            # Only booted simulators should be returned
            assert len(simulators) == 1
            assert simulators[0].name == "iPhone 15 Pro"
            assert simulators[0].device_type == "simulator"
            assert "17.2" in simulators[0].version

    def test_register_browserstack_session(self, resolver, browserstack_credentials):
        """Test registering a BrowserStack session."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot

        robot = BrowserStackRobot(browserstack_credentials, "session-123")
        device_id = resolver.register_browserstack_session("session-123", robot)

        assert device_id == "browserstack-session:session-123"
        assert "session-123" in resolver.browserstack_sessions

    def test_unregister_browserstack_session(self, resolver, browserstack_credentials):
        """Test unregistering a BrowserStack session."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot

        robot = BrowserStackRobot(browserstack_credentials, "session-123")
        resolver.browserstack_sessions["session-123"] = robot

        result = resolver.unregister_browserstack_session("session-123")
        assert result is True
        assert "session-123" not in resolver.browserstack_sessions

    def test_unregister_browserstack_session_with_prefix(
        self, resolver, browserstack_credentials
    ):
        """Test unregistering with full device ID."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot

        robot = BrowserStackRobot(browserstack_credentials, "session-123")
        resolver.browserstack_sessions["session-123"] = robot

        result = resolver.unregister_browserstack_session(
            "browserstack-session:session-123"
        )
        assert result is True

    def test_unregister_browserstack_session_not_found(self, resolver):
        """Test unregistering nonexistent session."""
        result = resolver.unregister_browserstack_session("nonexistent")
        assert result is False

    def test_list_browserstack_sessions(self, resolver, browserstack_credentials):
        """Test listing BrowserStack sessions."""
        from mobile_mcp.robots.browserstack import BrowserStackRobot

        robot1 = BrowserStackRobot(browserstack_credentials, "session-1")
        robot2 = BrowserStackRobot(browserstack_credentials, "session-2")
        resolver.browserstack_sessions["session-1"] = robot1
        resolver.browserstack_sessions["session-2"] = robot2

        sessions = resolver.list_browserstack_sessions()
        assert len(sessions) == 2
        assert "session-1" in sessions
        assert "session-2" in sessions
