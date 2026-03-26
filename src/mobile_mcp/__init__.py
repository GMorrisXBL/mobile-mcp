"""Mobile MCP - Model Context Protocol server for mobile automation."""

from mobile_mcp.server import create_mcp_server, get_version

__version__ = get_version()

__all__ = [
    "__version__",
    "create_mcp_server",
    "get_version",
]
