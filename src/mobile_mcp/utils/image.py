"""Image processing utilities for Mobile MCP."""

import io
import os
from typing import Literal, Optional

from PIL import Image

from mobile_mcp.logger import trace


ImageFormat = Literal["png", "jpeg"]


def get_screenshot_config() -> tuple[ImageFormat, int]:
    """Get screenshot format and quality from environment.

    Returns:
        Tuple of (format, quality).
    """
    format_str = os.environ.get("SCREENSHOT_FORMAT", "jpeg").lower()
    format_type: ImageFormat = "jpeg" if format_str == "jpeg" else "png"

    quality_str = os.environ.get("SCREENSHOT_QUALITY", "75")
    try:
        quality = max(1, min(100, int(quality_str)))
    except ValueError:
        quality = 75

    return format_type, quality


def process_screenshot(
    png_data: bytes,
    target_width: Optional[int] = None,
    format: Optional[ImageFormat] = None,
    quality: Optional[int] = None,
) -> tuple[bytes, str]:
    """Process a screenshot: resize and/or convert format.

    Args:
        png_data: Raw PNG screenshot data.
        target_width: Target width for resizing (maintains aspect ratio).
        format: Output format ("png" or "jpeg"). Uses env config if None.
        quality: JPEG quality (1-100). Uses env config if None.

    Returns:
        Tuple of (processed_bytes, mime_type).
    """
    # Get config from environment if not specified
    if format is None or quality is None:
        env_format, env_quality = get_screenshot_config()
        format = format or env_format
        quality = quality or env_quality

    img = Image.open(io.BytesIO(png_data))
    original_size = len(png_data)

    # Resize if target width specified
    if target_width and img.width > target_width:
        ratio = target_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
        trace(f"Resized image from {img.width}x{img.height} to {target_width}x{new_height}")

    # Convert and save
    output = io.BytesIO()

    if format == "jpeg":
        # Convert RGBA to RGB for JPEG
        if img.mode in ("RGBA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            img = background

        img.save(output, format="JPEG", quality=quality, optimize=True)
        mime_type = "image/jpeg"
    else:
        img.save(output, format="PNG", optimize=True)
        mime_type = "image/png"

    result = output.getvalue()
    trace(f"Screenshot processed: {original_size} -> {len(result)} bytes ({format})")

    return result, mime_type


def get_image_dimensions(png_data: bytes) -> tuple[int, int]:
    """Get dimensions of a PNG image.

    Args:
        png_data: Raw PNG data.

    Returns:
        Tuple of (width, height).
    """
    img = Image.open(io.BytesIO(png_data))
    return img.width, img.height


def validate_png(png_data: bytes) -> bool:
    """Validate that data is a valid PNG image.

    Args:
        png_data: Raw image data.

    Returns:
        True if valid PNG, False otherwise.
    """
    try:
        img = Image.open(io.BytesIO(png_data))
        img.verify()
        return True
    except Exception:
        return False
