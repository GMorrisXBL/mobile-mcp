"""Validation utilities for Mobile MCP."""

import os
from pathlib import Path

from mobile_mcp.robots.base import ActionableError


def validate_output_path(path: str) -> None:
    """Validate that an output path is writable.

    Args:
        path: The file path to validate.

    Raises:
        ActionableError: If the path is not writable.
    """
    output_path = Path(path)
    parent_dir = output_path.parent

    if not parent_dir.exists():
        raise ActionableError(
            f"Directory does not exist: {parent_dir}. "
            "Please create the directory first or choose a different path."
        )

    if not os.access(parent_dir, os.W_OK):
        raise ActionableError(
            f"Directory is not writable: {parent_dir}. "
            "Please check permissions or choose a different path."
        )


def validate_file_extension(path: str, allowed_extensions: list[str], operation: str) -> None:
    """Validate that a file has an allowed extension.

    Args:
        path: The file path to validate.
        allowed_extensions: List of allowed extensions (e.g., [".png", ".jpg"]).
        operation: Name of the operation for error messages.

    Raises:
        ActionableError: If the extension is not allowed.
    """
    ext = Path(path).suffix.lower()
    if ext not in allowed_extensions:
        allowed = ", ".join(allowed_extensions)
        raise ActionableError(
            f"Invalid file extension for {operation}: '{ext}'. "
            f"Allowed extensions: {allowed}"
        )


def validate_file_exists(path: str) -> None:
    """Validate that a file exists.

    Args:
        path: The file path to validate.

    Raises:
        ActionableError: If the file does not exist.
    """
    if not Path(path).exists():
        raise ActionableError(f"File not found: {path}")


def validate_app_path(path: str) -> None:
    """Validate an app installation path.

    Args:
        path: The app file path to validate.

    Raises:
        ActionableError: If the path is invalid.
    """
    validate_file_exists(path)
    ext = Path(path).suffix.lower()
    valid_extensions = [".apk", ".ipa", ".app", ".zip"]

    if ext not in valid_extensions:
        raise ActionableError(
            f"Invalid app file: '{path}'. "
            f"Expected one of: {', '.join(valid_extensions)}"
        )
