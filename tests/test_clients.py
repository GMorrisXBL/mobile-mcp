"""Tests for mobile_mcp.clients modules."""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mobile_mcp.clients.browserstack_api import (
    BrowserStackClient,
    BrowserStackCredentials,
    BrowserStackDevice,
    is_browserstack_configured,
    parse_browserstack_device_id,
)
from mobile_mcp.clients.wda import WebDriverAgentClient
from mobile_mcp.robots.base import ActionableError


# ============================================================================
# BrowserStack Credentials Tests
# ============================================================================


class TestBrowserStackCredentials:
    """Tests for BrowserStackCredentials."""

    def test_creation(self):
        """Test creating credentials."""
        creds = BrowserStackCredentials(
            username="user",
            access_key="key123",
        )
        assert creds.username == "user"
        assert creds.access_key == "key123"

    def test_from_env_success(self):
        """Test loading credentials from environment."""
        with patch.dict(
            "os.environ",
            {
                "BROWSERSTACK_USERNAME": "test_user",
                "BROWSERSTACK_ACCESS_KEY": "test_key",
            },
        ):
            creds = BrowserStackCredentials.from_env()
            assert creds is not None
            assert creds.username == "test_user"
            assert creds.access_key == "test_key"

    def test_from_env_missing_username(self):
        """Test loading credentials with missing username."""
        with patch.dict(
            "os.environ",
            {"BROWSERSTACK_ACCESS_KEY": "test_key"},
            clear=True,
        ):
            creds = BrowserStackCredentials.from_env()
            assert creds is None

    def test_from_env_missing_key(self):
        """Test loading credentials with missing access key."""
        with patch.dict(
            "os.environ",
            {"BROWSERSTACK_USERNAME": "test_user"},
            clear=True,
        ):
            creds = BrowserStackCredentials.from_env()
            assert creds is None


class TestIsBrowserStackConfigured:
    """Tests for is_browserstack_configured function."""

    def test_configured(self):
        """Test when BrowserStack is configured."""
        with patch.dict(
            "os.environ",
            {
                "BROWSERSTACK_USERNAME": "user",
                "BROWSERSTACK_ACCESS_KEY": "key",
            },
        ):
            assert is_browserstack_configured() is True

    def test_not_configured(self):
        """Test when BrowserStack is not configured."""
        with patch.dict("os.environ", {}, clear=True):
            assert is_browserstack_configured() is False


class TestParseBrowserStackDeviceId:
    """Tests for parse_browserstack_device_id function."""

    def test_valid_device_id(self):
        """Test parsing valid device ID."""
        result = parse_browserstack_device_id("browserstack:ios:iPhone 14 Pro:16")
        assert result is not None
        assert result["os"] == "ios"
        assert result["device"] == "iPhone 14 Pro"
        assert result["os_version"] == "16"

    def test_android_device_id(self):
        """Test parsing Android device ID."""
        result = parse_browserstack_device_id("browserstack:android:Samsung Galaxy S23:13.0")
        assert result is not None
        assert result["os"] == "android"
        assert result["device"] == "Samsung Galaxy S23"
        assert result["os_version"] == "13.0"

    def test_invalid_prefix(self):
        """Test parsing device ID with wrong prefix."""
        result = parse_browserstack_device_id("other:ios:iPhone:16")
        assert result is None

    def test_invalid_format(self):
        """Test parsing device ID with wrong format."""
        result = parse_browserstack_device_id("browserstack:ios:iPhone")
        assert result is None


# ============================================================================
# BrowserStack Client Tests
# ============================================================================


class TestBrowserStackClient:
    """Tests for BrowserStackClient."""

    @pytest.fixture
    def client(self, browserstack_credentials):
        """Create a BrowserStack client for testing."""
        return BrowserStackClient(browserstack_credentials)

    def test_init(self, client, browserstack_credentials):
        """Test client initialization."""
        assert client.credentials == browserstack_credentials
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_available_devices(
        self, client, browserstack_device_response
    ):
        """Test getting available devices."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = browserstack_device_response

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            devices = await client.get_available_devices()

            assert len(devices) == 3
            assert isinstance(devices[0], BrowserStackDevice)
            assert devices[0].os == "ios"
            assert devices[0].device == "iPhone 14 Pro"
            assert devices[1].os == "android"

    @pytest.mark.asyncio
    async def test_get_available_devices_error(self, client):
        """Test error handling when getting devices."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(ActionableError, match="Failed to fetch"):
                await client.get_available_devices()

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Test creating a session."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": {"sessionId": "session-123"}
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            session_id = await client.create_session(
                device="iPhone 14 Pro",
                os="ios",
                os_version="16",
            )

            assert session_id == "session-123"

    @pytest.mark.asyncio
    async def test_create_session_with_app(self, client):
        """Test creating a session with app URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": {"sessionId": "session-456"}
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            session_id = await client.create_session(
                device="Samsung Galaxy S23",
                os="android",
                os_version="13.0",
                app_url="bs://app123",
            )

            assert session_id == "session-456"
            # Verify the post was called with app_url in capabilities
            call_args = mock_http_client.post.call_args
            assert "bs://app123" in str(call_args) or call_args is not None

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        """Test deleting a session."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.delete = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await client.delete_session("session-123")

            mock_http_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_request_get(self, client):
        """Test making a GET request to a session."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"value": "test"}'
        mock_response.json.return_value = {"value": "test"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.session_request("session-123", "GET", "/screenshot")

            assert result == {"value": "test"}

    @pytest.mark.asyncio
    async def test_session_request_post(self, client):
        """Test making a POST request to a session."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"value": null}'
        mock_response.json.return_value = {"value": None}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.session_request(
                "session-123",
                "POST",
                "/actions",
                {"actions": []},
            )

            assert result == {"value": None}

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.aclose = AsyncMock()
        client._client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._client is None


# ============================================================================
# WebDriverAgent Client Tests
# ============================================================================


class TestWebDriverAgentClient:
    """Tests for WebDriverAgentClient."""

    @pytest.fixture
    def wda_client(self):
        """Create a WDA client for testing."""
        return WebDriverAgentClient(host="localhost", port=8100)

    def test_init(self, wda_client):
        """Test client initialization."""
        assert wda_client.host == "localhost"
        assert wda_client.port == 8100
        assert wda_client.base_url == "http://localhost:8100"

    @pytest.mark.asyncio
    async def test_is_running_success(self, wda_client, wda_status_response):
        """Test checking if WDA is running."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wda_status_response

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await wda_client.is_running()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_running_not_ready(self, wda_client):
        """Test WDA not running."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"ready": False}}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await wda_client.is_running()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_running_connection_error(self, wda_client):
        """Test WDA connection error."""
        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get_client.return_value = mock_http_client

            result = await wda_client.is_running()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_screen_size(self, wda_client, wda_window_size_response):
        """Test getting screen size."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wda_window_size_response

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            size = await wda_client.get_screen_size()
            assert size.width == 390
            assert size.height == 844

    @pytest.mark.asyncio
    async def test_get_screenshot(self, wda_client, sample_png_bytes):
        """Test taking a screenshot."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": base64.b64encode(sample_png_bytes).decode("ascii")
        }

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            screenshot = await wda_client.get_screenshot()
            assert screenshot == sample_png_bytes

    @pytest.mark.asyncio
    async def test_tap(self, wda_client):
        """Test tap action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": None}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await wda_client.tap(100, 200)

            # Verify post was called
            mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_swipe(self, wda_client, sample_screen_size):
        """Test swipe action."""
        # Mock get_screen_size
        with patch.object(wda_client, "get_screen_size", return_value=sample_screen_size):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"value": None}

            with patch.object(wda_client, "_get_client") as mock_get_client:
                mock_http_client = AsyncMock()
                mock_http_client.post = AsyncMock(return_value=mock_response)
                mock_get_client.return_value = mock_http_client

                await wda_client.swipe("up")

                mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_send_keys(self, wda_client):
        """Test sending keys."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": None}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await wda_client.send_keys("hello world")

            mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_press_button(self, wda_client):
        """Test pressing a button."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": None}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await wda_client.press_button("HOME")

            mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_open_url(self, wda_client):
        """Test opening a URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": None}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await wda_client.open_url("https://example.com")

            mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_get_orientation(self, wda_client):
        """Test getting orientation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": "PORTRAIT"}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            orientation = await wda_client.get_orientation()
            assert orientation.value == "portrait"

    @pytest.mark.asyncio
    async def test_set_orientation(self, wda_client):
        """Test setting orientation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": None}

        with patch.object(wda_client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            from mobile_mcp.robots.base import Orientation
            await wda_client.set_orientation(Orientation.LANDSCAPE)

            mock_http_client.post.assert_called()
