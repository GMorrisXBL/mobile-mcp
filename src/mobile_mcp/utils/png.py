"""PNG parsing utilities for Mobile MCP."""

import struct
from typing import Optional

from mobile_mcp.robots.base import ActionableError


class PNG:
    """Simple PNG parser for extracting dimensions without full image decode."""

    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def __init__(self, data: bytes):
        """Initialize PNG parser with raw data.

        Args:
            data: Raw PNG file data.

        Raises:
            ActionableError: If data is not a valid PNG.
        """
        self.data = data
        self._validate()

    def _validate(self) -> None:
        """Validate PNG signature."""
        if len(self.data) < 8:
            raise ActionableError("Invalid PNG: file too small")

        if self.data[:8] != self.PNG_SIGNATURE:
            raise ActionableError("Invalid PNG: incorrect signature")

    def get_dimensions(self) -> tuple[int, int]:
        """Extract image dimensions from IHDR chunk.

        Returns:
            Tuple of (width, height).

        Raises:
            ActionableError: If IHDR chunk not found or invalid.
        """
        # IHDR chunk should be immediately after signature
        # Chunk structure: length (4 bytes) + type (4 bytes) + data + CRC (4 bytes)
        if len(self.data) < 24:
            raise ActionableError("Invalid PNG: file too small for IHDR")

        # Check for IHDR chunk type at offset 12 (after 8-byte signature + 4-byte length)
        chunk_type = self.data[12:16]
        if chunk_type != b"IHDR":
            raise ActionableError("Invalid PNG: IHDR chunk not found")

        # Width and height are at offset 16 (big-endian 4-byte integers)
        width = struct.unpack(">I", self.data[16:20])[0]
        height = struct.unpack(">I", self.data[20:24])[0]

        return width, height


def get_png_dimensions(data: bytes) -> tuple[int, int]:
    """Get PNG image dimensions from raw bytes.

    Convenience function that wraps the PNG class.

    Args:
        data: Raw PNG file data.

    Returns:
        Tuple of (width, height).

    Raises:
        ActionableError: If data is not a valid PNG.
    """
    png = PNG(data)
    return png.get_dimensions()
