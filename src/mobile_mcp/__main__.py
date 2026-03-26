"""CLI entry point for mobile-mcp server."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Literal

from .logger import configure_logging, get_logger
from .server import create_mcp_server

logger = get_logger(__name__)


def main() -> None:
    """Main entry point for the mobile-mcp CLI."""
    parser = argparse.ArgumentParser(
        prog="mobile-mcp",
        description="MCP server for mobile device automation",
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (default) or http",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for HTTP transport (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind for HTTP transport (default: 8080)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-file",
        help="Path to log file (logs to stderr by default)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        from .server import get_version
        print(f"mobile-mcp {get_version()}")
        sys.exit(0)

    # Configure logging
    configure_logging(
        level=args.log_level,
        log_file=args.log_file,
    )

    # Create and run server
    mcp = create_mcp_server()

    if args.transport == "stdio":
        logger.info("Starting mobile-mcp server with stdio transport")
        run_stdio(mcp)
    else:
        logger.info(f"Starting mobile-mcp server with HTTP transport on {args.host}:{args.port}")
        run_http(mcp, args.host, args.port)


def run_stdio(mcp) -> None:
    """Run the MCP server with stdio transport.

    Args:
        mcp: FastMCP server instance
    """
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


def run_http(mcp, host: str, port: int) -> None:
    """Run the MCP server with HTTP transport.

    Args:
        mcp: FastMCP server instance
        host: Host to bind
        port: Port to bind
    """
    try:
        # FastMCP supports SSE transport for HTTP
        mcp.run(transport="sse", host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
