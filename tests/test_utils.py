"""Tests for mobile_mcp.utils modules."""

import io
import os
import struct
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from mobile_mcp.robots.base import ActionableError
from mobile_mcp.utils.png import PNG, get_png_dimensions
from mobile_mcp.utils.image import (
    get_image_dimensions,
    get_screenshot_config,
    process_screenshot,
    validate_png,
)
from mobile_mcp.utils.validation import validate_file_extension, validate_output_path
from mobile_mcp.utils.subprocess_utils import (
    CommandResult,
    find_executable,
    run_command,
    run_command_raw,
    run_command_sync,
)


# ============================================================================
# PNG Tests
# ============================================================================


class TestPNG:
    """Tests for PNG class."""

    def test_valid_png(self, sample_png_bytes):
        """Test parsing valid PNG."""
        png = PNG(sample_png_bytes)
        width, height = png.get_dimensions()
        assert width == 100
        assert height == 100

    def test_large_png(self, sample_png_bytes_large):
        """Test parsing PNG with larger dimensions."""
        png = PNG(sample_png_bytes_large)
        width, height = png.get_dimensions()
        assert width == 1170
        assert height == 2532

    def test_invalid_signature(self):
        """Test PNG with invalid signature."""
        invalid_data = b"NOT A PNG FILE"
        with pytest.raises(ActionableError, match="incorrect signature"):
            PNG(invalid_data)

    def test_too_small(self):
        """Test PNG that is too small."""
        with pytest.raises(ActionableError, match="file too small"):
            PNG(b"\x89PNG")

    def test_missing_ihdr(self):
        """Test PNG without IHDR chunk."""
        # Valid signature but wrong chunk type
        signature = b"\x89PNG\r\n\x1a\n"
        fake_chunk = struct.pack(">I", 13) + b"FAKE" + b"\x00" * 13 + struct.pack(">I", 0)
        with pytest.raises(ActionableError, match="IHDR chunk not found"):
            PNG(signature + fake_chunk)


class TestGetPngDimensions:
    """Tests for get_png_dimensions function."""

    def test_convenience_function(self, sample_png_bytes):
        """Test get_png_dimensions convenience function."""
        width, height = get_png_dimensions(sample_png_bytes)
        assert width == 100
        assert height == 100

    def test_invalid_png(self):
        """Test get_png_dimensions with invalid PNG."""
        with pytest.raises(ActionableError):
            get_png_dimensions(b"invalid")


# ============================================================================
# Image Processing Tests
# ============================================================================


class TestGetScreenshotConfig:
    """Tests for get_screenshot_config function."""

    def test_default_config(self):
        """Test default configuration."""
        with patch.dict(os.environ, {}, clear=True):
            fmt, quality = get_screenshot_config()
            assert fmt == "jpeg"
            assert quality == 75

    def test_custom_format_png(self):
        """Test PNG format configuration."""
        with patch.dict(os.environ, {"SCREENSHOT_FORMAT": "png"}):
            fmt, quality = get_screenshot_config()
            assert fmt == "png"

    def test_custom_format_jpeg(self):
        """Test JPEG format configuration."""
        with patch.dict(os.environ, {"SCREENSHOT_FORMAT": "JPEG"}):
            fmt, quality = get_screenshot_config()
            assert fmt == "jpeg"

    def test_custom_quality(self):
        """Test custom quality configuration."""
        with patch.dict(os.environ, {"SCREENSHOT_QUALITY": "90"}):
            fmt, quality = get_screenshot_config()
            assert quality == 90

    def test_quality_bounds(self):
        """Test quality is bounded between 1 and 100."""
        with patch.dict(os.environ, {"SCREENSHOT_QUALITY": "150"}):
            fmt, quality = get_screenshot_config()
            assert quality == 100

        with patch.dict(os.environ, {"SCREENSHOT_QUALITY": "0"}):
            fmt, quality = get_screenshot_config()
            assert quality == 1

    def test_invalid_quality(self):
        """Test invalid quality value falls back to default."""
        with patch.dict(os.environ, {"SCREENSHOT_QUALITY": "invalid"}):
            fmt, quality = get_screenshot_config()
            assert quality == 75


class TestProcessScreenshot:
    """Tests for process_screenshot function."""

    @pytest.fixture
    def real_png_bytes(self):
        """Create a real valid PNG image for testing."""
        img = Image.new("RGB", (200, 400), color="red")
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

    def test_convert_to_jpeg(self, real_png_bytes):
        """Test converting PNG to JPEG."""
        result, mime_type = process_screenshot(real_png_bytes, format="jpeg", quality=75)
        
        assert mime_type == "image/jpeg"
        # Verify it's valid JPEG by loading with PIL
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_keep_as_png(self, real_png_bytes):
        """Test keeping image as PNG."""
        result, mime_type = process_screenshot(real_png_bytes, format="png")
        
        assert mime_type == "image/png"
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"

    def test_resize_image(self, real_png_bytes):
        """Test resizing image."""
        result, mime_type = process_screenshot(
            real_png_bytes,
            target_width=100,
            format="png",
        )
        
        img = Image.open(io.BytesIO(result))
        assert img.width == 100
        # Height should maintain aspect ratio (original was 200x400)
        assert img.height == 200

    def test_no_resize_if_smaller(self, real_png_bytes):
        """Test no resize if image is smaller than target."""
        result, mime_type = process_screenshot(
            real_png_bytes,
            target_width=500,  # Larger than 200
            format="png",
        )
        
        img = Image.open(io.BytesIO(result))
        assert img.width == 200  # Original width

    def test_uses_env_config(self, real_png_bytes):
        """Test using environment configuration."""
        with patch.dict(os.environ, {"SCREENSHOT_FORMAT": "png", "SCREENSHOT_QUALITY": "50"}):
            result, mime_type = process_screenshot(real_png_bytes)
            assert mime_type == "image/png"


class TestValidatePng:
    """Tests for validate_png function."""

    def test_valid_png(self):
        """Test validation of valid PNG."""
        img = Image.new("RGB", (10, 10), color="blue")
        output = io.BytesIO()
        img.save(output, format="PNG")
        
        assert validate_png(output.getvalue()) is True

    def test_invalid_png(self):
        """Test validation of invalid PNG."""
        assert validate_png(b"not a png") is False


class TestGetImageDimensions:
    """Tests for get_image_dimensions function."""

    def test_get_dimensions(self):
        """Test getting image dimensions."""
        img = Image.new("RGB", (150, 300), color="green")
        output = io.BytesIO()
        img.save(output, format="PNG")
        
        width, height = get_image_dimensions(output.getvalue())
        assert width == 150
        assert height == 300


# ============================================================================
# Validation Tests
# ============================================================================


class TestValidateFileExtension:
    """Tests for validate_file_extension function."""

    def test_valid_extension(self):
        """Test valid file extension."""
        # Should not raise
        validate_file_extension("/path/to/file.png", [".png", ".jpg"], "test")
        validate_file_extension("/path/to/file.jpg", [".png", ".jpg"], "test")
        validate_file_extension("/path/to/file.JPEG", [".png", ".jpg", ".jpeg"], "test")

    def test_invalid_extension(self):
        """Test invalid file extension."""
        with pytest.raises(ActionableError, match="must have one of these extensions"):
            validate_file_extension("/path/to/file.gif", [".png", ".jpg"], "test")

    def test_no_extension(self):
        """Test file without extension."""
        with pytest.raises(ActionableError):
            validate_file_extension("/path/to/file", [".png"], "test")


class TestValidateOutputPath:
    """Tests for validate_output_path function."""

    def test_valid_path(self, tmp_path):
        """Test valid output path."""
        output_file = tmp_path / "output.png"
        # Should not raise
        validate_output_path(str(output_file))

    def test_nonexistent_directory(self):
        """Test path with nonexistent directory."""
        with pytest.raises(ActionableError, match="does not exist"):
            validate_output_path("/nonexistent/directory/file.png")


# ============================================================================
# Subprocess Tests
# ============================================================================


class TestRunCommandSync:
    """Tests for run_command_sync function."""

    def test_successful_command(self):
        """Test successful command execution."""
        result = run_command_sync(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_command_with_check(self):
        """Test command with check=True raises on failure."""
        with pytest.raises(ActionableError):
            run_command_sync(["false"], check=True)

    def test_command_without_check(self):
        """Test command with check=False returns result on failure."""
        result = run_command_sync(["false"], check=False)
        assert result.returncode != 0

    def test_command_result_structure(self):
        """Test CommandResult structure."""
        result = run_command_sync(["echo", "test"])
        assert isinstance(result, CommandResult)
        assert hasattr(result, "returncode")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")


class TestRunCommandAsync:
    """Tests for async run_command function."""

    @pytest.mark.asyncio
    async def test_successful_command(self):
        """Test successful async command execution."""
        stdout, stderr = await run_command("echo", "hello")
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_command_failure(self):
        """Test async command failure raises ActionableError."""
        with pytest.raises(ActionableError):
            await run_command("false")

    @pytest.mark.asyncio
    async def test_command_with_check_false(self):
        """Test async command with check=False."""
        stdout, stderr = await run_command("false", check=False)
        # Should not raise

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test command timeout."""
        with pytest.raises(ActionableError, match="timed out"):
            await run_command("sleep", "10", timeout=0.1)


class TestRunCommandRaw:
    """Tests for run_command_raw function."""

    @pytest.mark.asyncio
    async def test_returns_bytes(self):
        """Test run_command_raw returns bytes."""
        result = await run_command_raw("echo", "hello")
        assert isinstance(result, bytes)
        assert b"hello" in result


class TestFindExecutable:
    """Tests for find_executable function."""

    def test_find_existing_executable(self):
        """Test finding an existing executable."""
        # 'echo' should exist on all systems
        result = find_executable("echo")
        assert result is not None

    def test_find_nonexistent_executable(self):
        """Test finding a nonexistent executable."""
        result = find_executable("nonexistent_command_xyz")
        assert result is None

    def test_env_var_override(self):
        """Test environment variable override."""
        with patch.dict(os.environ, {"TEST_PATH": "/custom/path/to/cmd"}):
            with patch("os.path.isfile", return_value=True):
                with patch("os.access", return_value=True):
                    result = find_executable("cmd", env_var="TEST_PATH")
                    assert result == "/custom/path/to/cmd"
