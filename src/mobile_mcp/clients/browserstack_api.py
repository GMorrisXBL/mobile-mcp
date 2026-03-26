"""BrowserStack API client for App Automate.

Handles authentication, device listing, session management, and app upload.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..robots.base import ActionableError

BROWSERSTACK_HUB = "https://hub-cloud.browserstack.com/wd/hub"
BROWSERSTACK_API = "https://api-cloud.browserstack.com"


@dataclass
class BrowserStackCredentials:
    """BrowserStack authentication credentials."""

    username: str
    access_key: str

    @classmethod
    def from_env(cls) -> BrowserStackCredentials | None:
        """Load credentials from environment variables.

        Requires:
            BROWSERSTACK_USERNAME - Your BrowserStack username
            BROWSERSTACK_ACCESS_KEY - Your BrowserStack access key
        """
        username = os.environ.get("BROWSERSTACK_USERNAME")
        access_key = os.environ.get("BROWSERSTACK_ACCESS_KEY")

        if not username or not access_key:
            return None

        return cls(username=username, access_key=access_key)


@dataclass
class BrowserStackDevice:
    """Available BrowserStack device."""

    id: str
    device: str
    os: str
    os_version: str
    real_mobile: bool


@dataclass
class BrowserStackSession:
    """Active BrowserStack session."""

    session_id: str
    device: str
    os: str
    os_version: str


def is_browserstack_configured() -> bool:
    """Check if BrowserStack credentials are configured."""
    return BrowserStackCredentials.from_env() is not None


def parse_browserstack_device_id(device_id: str) -> dict[str, str] | None:
    """Parse a BrowserStack device ID back to its components.

    Args:
        device_id: Device ID in format 'browserstack:os:device:version'

    Returns:
        Dictionary with os, device, os_version keys, or None if invalid
    """
    if not device_id.startswith("browserstack:"):
        return None

    parts = device_id.split(":")
    if len(parts) != 4:
        return None

    return {
        "os": parts[1],
        "device": parts[2],
        "os_version": parts[3],
    }


class BrowserStackClient:
    """HTTP client for BrowserStack App Automate API."""

    def __init__(self, credentials: BrowserStackCredentials) -> None:
        """Initialize BrowserStack client.

        Args:
            credentials: BrowserStack authentication credentials
        """
        self.credentials = credentials
        self._client: httpx.AsyncClient | None = None

    def _get_auth_header(self) -> str:
        """Generate Basic auth header."""
        auth_str = f"{self.credentials.username}:{self.credentials.access_key}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        return f"Basic {encoded}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_available_devices(self) -> list[BrowserStackDevice]:
        """Get list of available devices from BrowserStack.

        Returns:
            List of available BrowserStack devices
        """
        client = await self._get_client()
        response = await client.get(f"{BROWSERSTACK_API}/app-automate/devices.json")

        if response.status_code != 200:
            raise ActionableError(
                f"Failed to fetch BrowserStack devices: {response.status_code}"
            )

        devices = response.json()
        return [
            BrowserStackDevice(
                id=f"browserstack:{d['os']}:{d['device']}:{d['os_version']}",
                device=d["device"],
                os=d["os"],
                os_version=d["os_version"],
                real_mobile=d.get("realMobile", True),
            )
            for d in devices
        ]

    async def create_session(
        self,
        device: str,
        os: str,
        os_version: str,
        app_url: str | None = None,
    ) -> str:
        """Create a new Appium session on BrowserStack.

        Args:
            device: Device name (e.g., "iPhone 14 Pro")
            os: Operating system ("ios" or "android")
            os_version: OS version (e.g., "16")
            app_url: Optional app URL (bs:// or app_url from upload)

        Returns:
            Session ID
        """
        capabilities: dict[str, Any] = {
            "bstack:options": {
                "userName": self.credentials.username,
                "accessKey": self.credentials.access_key,
                "deviceName": device,
                "osVersion": os_version,
                "realMobile": "true",
                "local": "false",
                "debug": "true",
                "networkLogs": "true",
            },
            "platformName": "iOS" if os.lower() == "ios" else "Android",
        }

        # Add app URL if provided
        app = app_url or os.environ.get("BROWSERSTACK_APP_URL")
        if app:
            capabilities["bstack:options"]["appUrl"] = app

        client = await self._get_client()
        response = await client.post(
            f"{BROWSERSTACK_HUB}/session",
            json={
                "capabilities": {
                    "alwaysMatch": capabilities,
                },
            },
        )

        if response.status_code != 200:
            error_text = response.text
            raise ActionableError(
                f"Failed to create BrowserStack session: {response.status_code} {error_text}"
            )

        result = response.json()
        return result["value"]["sessionId"]

    async def delete_session(self, session_id: str) -> None:
        """Delete a BrowserStack session.

        Args:
            session_id: Session ID to delete
        """
        client = await self._get_client()
        await client.delete(f"{BROWSERSTACK_HUB}/session/{session_id}")

    async def upload_app(self, file_path: str | Path) -> str:
        """Upload an app to BrowserStack.

        Args:
            file_path: Path to the app file (.apk, .ipa, .aab)

        Returns:
            App URL (bs:// or app_url) for use in sessions
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise ActionableError(f"App file not found: {file_path}")

        # Read file content
        file_content = file_path.read_bytes()
        file_name = file_path.name

        # Build multipart form data
        client = await self._get_client()

        # Use a separate client for file upload with multipart headers
        async with httpx.AsyncClient(
            headers={"Authorization": self._get_auth_header()},
            timeout=httpx.Timeout(300.0),  # 5 min timeout for uploads
        ) as upload_client:
            response = await upload_client.post(
                f"{BROWSERSTACK_API}/app-automate/upload",
                files={"file": (file_name, file_content, "application/octet-stream")},
            )

        if response.status_code != 200:
            error_text = response.text
            raise ActionableError(
                f"Failed to upload app to BrowserStack: {response.status_code} {error_text}"
            )

        result = response.json()
        return result["app_url"]

    async def session_request(
        self,
        session_id: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request to a BrowserStack session.

        Args:
            session_id: Active session ID
            method: HTTP method (GET, POST, DELETE)
            path: API path (appended to /session/{session_id})
            body: Optional JSON body

        Returns:
            Response JSON or None
        """
        client = await self._get_client()
        url = f"{BROWSERSTACK_HUB}/session/{session_id}{path}"

        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=body)
        elif method == "DELETE":
            response = await client.delete(url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if response.status_code not in (200, 204):
            error_text = response.text
            raise ActionableError(
                f"BrowserStack request failed: {response.status_code} {error_text}"
            )

        text = response.text
        if not text:
            return None

        return response.json()
