"""Logging utilities for Mobile MCP."""

import logging
import os
import sys
from typing import Optional

# Configure logging
_logger: Optional[logging.Logger] = None
_configured = False


def _get_logger() -> logging.Logger:
    """Get or create the logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("mobile-mcp")
        _logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        _logger.addHandler(console_handler)

        # File handler if LOG_FILE is set
        log_file = os.environ.get("LOG_FILE")
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            _logger.addHandler(file_handler)

    return _logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional name for the logger. If None, returns the root mobile-mcp logger.

    Returns:
        Logger instance.
    """
    if name:
        return logging.getLogger(f"mobile-mcp.{name}")
    return _get_logger()


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """Configure logging settings.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to log file.
    """
    global _configured
    if _configured:
        return

    logger = _get_logger()

    # Set level on root logger
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Update console handler level
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(log_level)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _configured = True


def trace(message: str) -> None:
    """Log a trace/debug message."""
    _get_logger().debug(message)


def info(message: str) -> None:
    """Log an info message."""
    _get_logger().info(message)


def warning(message: str) -> None:
    """Log a warning message."""
    _get_logger().warning(message)


def error(message: str) -> None:
    """Log an error message."""
    _get_logger().error(message)
