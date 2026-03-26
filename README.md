# Mobile MCP

A Python-based [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for mobile device automation. Control iOS and Android devices—simulators, emulators, and real devices—through a unified interface.

## Features

- **Cross-platform**: iOS (Simulator + real devices) and Android (Emulator + real devices)
- **LLM-friendly**: Structured accessibility data, no computer vision required
- **BrowserStack integration**: Test on cloud-hosted real devices
- **Fast and lightweight**: Native accessibility trees for interactions

## Installation

Requires Python 3.11+.

```bash
# Using uv (recommended)
uv pip install mobile-mcp

# Or using pip
pip install mobile-mcp
```

### Prerequisites

- **iOS**: Xcode command line tools (`xcode-select --install`)
- **Android**: Android SDK Platform Tools (adb)
- **BrowserStack** (optional): Set `BROWSERSTACK_USERNAME` and `BROWSERSTACK_ACCESS_KEY` environment variables

## Quick Start

### Running the Server

```bash
# stdio transport (default, for MCP clients)
mobile-mcp

# HTTP transport (for development/debugging)
mobile-mcp --transport http --port 8080
```

### MCP Client Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "mobile-mcp": {
      "command": "mobile-mcp"
    }
  }
}
```

Or if installed via uvx:

```json
{
  "mcpServers": {
    "mobile-mcp": {
      "command": "uvx",
      "args": ["mobile-mcp"]
    }
  }
}
```

## Available Tools

### Device Management
| Tool | Description |
|------|-------------|
| `mobile_list_available_devices` | List all available devices (simulators, emulators, real devices) |
| `mobile_get_screen_size` | Get screen dimensions in pixels |
| `mobile_get_orientation` | Get current screen orientation |
| `mobile_set_orientation` | Change orientation (portrait/landscape) |

### App Management
| Tool | Description |
|------|-------------|
| `mobile_list_apps` | List installed apps on device |
| `mobile_launch_app` | Launch an app by package name |
| `mobile_terminate_app` | Stop a running app |
| `mobile_install_app` | Install an app (.apk, .ipa, .app) |
| `mobile_uninstall_app` | Uninstall an app |

### Screen Interaction
| Tool | Description |
|------|-------------|
| `mobile_take_screenshot` | Capture the current screen |
| `mobile_save_screenshot` | Save screenshot to file |
| `mobile_list_elements_on_screen` | Get UI elements with coordinates |
| `mobile_click_on_screen_at_coordinates` | Tap at x,y coordinates |
| `mobile_double_tap_on_screen` | Double-tap at coordinates |
| `mobile_long_press_on_screen_at_coordinates` | Long press at coordinates |
| `mobile_swipe_on_screen` | Swipe in a direction |

### Input & Navigation
| Tool | Description |
|------|-------------|
| `mobile_type_keys` | Type text into focused element |
| `mobile_press_button` | Press device buttons (HOME, BACK, etc.) |
| `mobile_open_url` | Open URL or deep link |

### Device Logs
| Tool | Description |
|------|-------------|
| `mobile_get_device_logs` | Get device logs (logcat/syslog) |
| `mobile_clear_device_logs` | Clear log buffer (Android) |

### BrowserStack (when configured)
| Tool | Description |
|------|-------------|
| `browserstack_list_devices` | List available cloud devices |
| `browserstack_start_session` | Start a remote test session |
| `browserstack_stop_session` | Stop a session |
| `browserstack_upload_app` | Upload app for testing |
| `browserstack_list_sessions` | List active sessions |

## CLI Options

```
mobile-mcp [OPTIONS]

Options:
  --transport {stdio,http}  Transport mode (default: stdio)
  --host HOST               HTTP host (default: 127.0.0.1)
  --port PORT               HTTP port (default: 8080)
  --log-level LEVEL         DEBUG, INFO, WARNING, ERROR (default: INFO)
  --log-file PATH           Log to file instead of stderr
  --version                 Show version and exit
```

## Development

```bash
# Clone the repository
git clone https://github.com/mobile-next/mobile-mcp.git
cd mobile-mcp

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Type checking
uv run mypy src

# Linting
uv run ruff check src
```

## Platform Support

| Platform | Status |
|----------|--------|
| iOS Simulator | Supported |
| iOS Real Device | Supported |
| Android Emulator | Supported |
| Android Real Device | Supported |
| BrowserStack | Supported |

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.
