"""Pytest configuration and shared fixtures."""

import asyncio
import base64
import json
import struct
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mobile_mcp.robots.base import (
    InstalledApp,
    Orientation,
    Rect,
    ScreenElement,
    ScreenSize,
    SwipeDirection,
)


# ============================================================================
# Async fixtures
# ============================================================================


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Sample data fixtures
# ============================================================================


@pytest.fixture
def sample_screen_size() -> ScreenSize:
    """Sample screen size for testing."""
    return ScreenSize(width=1170, height=2532, scale=3.0)


@pytest.fixture
def sample_screen_element() -> ScreenElement:
    """Sample screen element for testing."""
    return ScreenElement(
        type="Button",
        rect=Rect(x=100, y=200, width=150, height=50),
        text="Click Me",
        label="Submit Button",
        identifier="submit-btn",
    )


@pytest.fixture
def sample_installed_app() -> InstalledApp:
    """Sample installed app for testing."""
    return InstalledApp(
        app_name="Test App",
        package_name="com.example.testapp",
    )


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Generate valid minimal PNG bytes for testing."""
    # PNG signature
    signature = b"\x89PNG\r\n\x1a\n"
    
    # IHDR chunk (width=100, height=100, bit depth=8, color type=2 (RGB))
    ihdr_data = struct.pack(">IIBBBBB", 100, 100, 8, 2, 0, 0, 0)
    ihdr_crc = 0x12345678  # Placeholder CRC (not validated in our code)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    
    # IEND chunk
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0xAE426082)
    
    return signature + ihdr_chunk + iend_chunk


@pytest.fixture
def sample_png_bytes_large() -> bytes:
    """Generate PNG bytes with larger dimensions (1170x2532)."""
    signature = b"\x89PNG\r\n\x1a\n"
    
    ihdr_data = struct.pack(">IIBBBBB", 1170, 2532, 8, 2, 0, 0, 0)
    ihdr_crc = 0x12345678
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0xAE426082)
    
    return signature + ihdr_chunk + iend_chunk


# ============================================================================
# Mock fixtures for subprocess operations
# ============================================================================


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for sync command execution."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=0,
            stdout="success",
            stderr="",
        )
        yield mock


@pytest.fixture
def mock_asyncio_subprocess():
    """Mock asyncio subprocess for async command execution."""
    with patch("asyncio.create_subprocess_exec") as mock:
        process = AsyncMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"success", b""))
        process.wait = AsyncMock()
        process.kill = MagicMock()
        mock.return_value = process
        yield mock


# ============================================================================
# Mock fixtures for HTTP clients
# ============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient for HTTP requests."""
    with patch("httpx.AsyncClient") as mock_class:
        client = AsyncMock()
        client.is_closed = False
        client.aclose = AsyncMock()
        mock_class.return_value = client
        yield client


# ============================================================================
# Device fixtures
# ============================================================================


@pytest.fixture
def android_device_id() -> str:
    """Sample Android device ID."""
    return "emulator-5554"


@pytest.fixture
def ios_device_id() -> str:
    """Sample iOS device ID (UDID)."""
    return "00008030-001A35E83C38802E"


@pytest.fixture
def simulator_device_id() -> str:
    """Sample iOS simulator device ID."""
    return "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"


@pytest.fixture
def browserstack_session_id() -> str:
    """Sample BrowserStack session ID."""
    return "abc123def456"


# ============================================================================
# BrowserStack fixtures
# ============================================================================


@pytest.fixture
def browserstack_credentials():
    """Sample BrowserStack credentials."""
    from mobile_mcp.clients.browserstack_api import BrowserStackCredentials
    return BrowserStackCredentials(
        username="test_user",
        access_key="test_access_key",
    )


@pytest.fixture
def browserstack_device_response() -> list[dict]:
    """Sample BrowserStack devices API response."""
    return [
        {
            "device": "iPhone 14 Pro",
            "os": "ios",
            "os_version": "16",
            "realMobile": True,
        },
        {
            "device": "Samsung Galaxy S23",
            "os": "android",
            "os_version": "13.0",
            "realMobile": True,
        },
        {
            "device": "Google Pixel 7",
            "os": "android",
            "os_version": "13.0",
            "realMobile": True,
        },
    ]


# ============================================================================
# ADB/Go-iOS mock fixtures
# ============================================================================


@pytest.fixture
def mock_adb_devices_output() -> str:
    """Sample output from 'adb devices' command."""
    return """List of devices attached
emulator-5554	device
192.168.1.100:5555	device
"""


@pytest.fixture
def mock_go_ios_list_output() -> str:
    """Sample output from 'ios list' command."""
    return json.dumps({
        "deviceList": [
            "00008030-001A35E83C38802E",
            "00008020-002B46F94D48803F",
        ]
    })


@pytest.fixture
def mock_go_ios_info_output() -> str:
    """Sample output from 'ios info' command."""
    return json.dumps({
        "DeviceClass": "iPhone",
        "DeviceName": "Test iPhone",
        "ProductName": "iPhone OS",
        "ProductType": "iPhone14,2",
        "ProductVersion": "16.5",
        "PhoneNumber": None,
        "TimeZone": "America/Los_Angeles",
    })


@pytest.fixture
def mock_simctl_list_output() -> str:
    """Sample output from 'xcrun simctl list devices booted -j' command."""
    return json.dumps({
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-17-2": [
                {
                    "udid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
                    "name": "iPhone 15 Pro",
                    "state": "Booted",
                    "isAvailable": True,
                },
            ],
            "com.apple.CoreSimulator.SimRuntime.iOS-16-4": [
                {
                    "udid": "B2C3D4E5-F6A7-8901-BCDE-F12345678901",
                    "name": "iPhone 14",
                    "state": "Shutdown",
                    "isAvailable": True,
                },
            ],
        }
    })


# ============================================================================
# WDA mock fixtures
# ============================================================================


@pytest.fixture
def wda_status_response() -> dict:
    """Sample WDA status response."""
    return {
        "value": {
            "ready": True,
            "sessionId": "session-123",
        },
        "sessionId": "session-123",
    }


@pytest.fixture
def wda_session_response() -> dict:
    """Sample WDA create session response."""
    return {
        "value": {
            "sessionId": "session-123",
            "capabilities": {
                "device": "iphone",
                "browserName": "Safari",
            },
        },
        "sessionId": "session-123",
    }


@pytest.fixture
def wda_screenshot_response(sample_png_bytes) -> dict:
    """Sample WDA screenshot response."""
    return {
        "value": base64.b64encode(sample_png_bytes).decode("ascii"),
        "sessionId": "session-123",
    }


@pytest.fixture
def wda_window_size_response() -> dict:
    """Sample WDA window size response."""
    return {
        "value": {
            "width": 390,
            "height": 844,
        },
        "sessionId": "session-123",
    }


@pytest.fixture
def wda_source_response() -> dict:
    """Sample WDA source/UI hierarchy response."""
    return {
        "value": """<?xml version="1.0" encoding="UTF-8"?>
<AppiumAUT>
  <XCUIElementTypeApplication type="XCUIElementTypeApplication" name="TestApp">
    <XCUIElementTypeWindow type="XCUIElementTypeWindow">
      <XCUIElementTypeButton type="XCUIElementTypeButton" name="Submit" label="Submit" x="100" y="200" width="150" height="50"/>
      <XCUIElementTypeTextField type="XCUIElementTypeTextField" value="" x="50" y="300" width="300" height="40"/>
    </XCUIElementTypeWindow>
  </XCUIElementTypeApplication>
</AppiumAUT>""",
        "sessionId": "session-123",
    }
