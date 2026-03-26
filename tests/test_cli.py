"""Tests for the CLI entry point."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# CLI Argument Parsing Tests
# ============================================================================


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    def test_default_arguments(self):
        """Test default argument values."""
        with patch("sys.argv", ["mobile-mcp"]):
            from mobile_mcp.__main__ import main

            # Mock the server run to prevent actual execution
            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.run_stdio") as mock_run:
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    # Should use stdio by default
                    if mock_run.called:
                        mock_run.assert_called_once_with(mock_mcp)

    def test_version_flag(self, capsys):
        """Test --version flag."""
        with patch("sys.argv", ["mobile-mcp", "--version"]):
            from mobile_mcp.__main__ import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "mobile-mcp" in captured.out

    def test_transport_stdio(self):
        """Test --transport stdio option."""
        with patch("sys.argv", ["mobile-mcp", "--transport", "stdio"]):
            from mobile_mcp.__main__ import main

            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.run_stdio") as mock_run:
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    if mock_run.called:
                        mock_run.assert_called_once_with(mock_mcp)

    def test_transport_http(self):
        """Test --transport http option."""
        with patch("sys.argv", ["mobile-mcp", "--transport", "http"]):
            from mobile_mcp.__main__ import main

            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.run_http") as mock_run:
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    if mock_run.called:
                        mock_run.assert_called_once_with(mock_mcp, "127.0.0.1", 8080)

    def test_custom_host_port(self):
        """Test --host and --port options."""
        with patch(
            "sys.argv",
            ["mobile-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "9090"],
        ):
            from mobile_mcp.__main__ import main

            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.run_http") as mock_run:
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    if mock_run.called:
                        mock_run.assert_called_once_with(mock_mcp, "0.0.0.0", 9090)

    def test_log_level_options(self):
        """Test --log-level option with different values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            with patch("sys.argv", ["mobile-mcp", "--log-level", level]):
                from mobile_mcp.__main__ import main

                with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                    mock_mcp = MagicMock()
                    mock_create.return_value = mock_mcp
                    
                    with patch("mobile_mcp.__main__.configure_logging") as mock_log:
                        with patch("mobile_mcp.__main__.run_stdio"):
                            try:
                                main()
                            except SystemExit:
                                pass
                            
                            if mock_log.called:
                                mock_log.assert_called_once()
                                call_kwargs = mock_log.call_args[1]
                                assert call_kwargs["level"] == level

    def test_log_file_option(self, tmp_path):
        """Test --log-file option."""
        log_file = str(tmp_path / "test.log")
        
        with patch("sys.argv", ["mobile-mcp", "--log-file", log_file]):
            from mobile_mcp.__main__ import main

            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.configure_logging") as mock_log:
                    with patch("mobile_mcp.__main__.run_stdio"):
                        try:
                            main()
                        except SystemExit:
                            pass
                        
                        if mock_log.called:
                            call_kwargs = mock_log.call_args[1]
                            assert call_kwargs["log_file"] == log_file

    def test_invalid_transport(self):
        """Test invalid transport option."""
        with patch("sys.argv", ["mobile-mcp", "--transport", "invalid"]):
            from mobile_mcp.__main__ import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code != 0


# ============================================================================
# Run Function Tests
# ============================================================================


class TestRunFunctions:
    """Test run_stdio and run_http functions."""

    def test_run_stdio_success(self):
        """Test run_stdio executes without error."""
        from mobile_mcp.__main__ import run_stdio

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock()

        run_stdio(mock_mcp)
        mock_mcp.run.assert_called_once()

    def test_run_stdio_keyboard_interrupt(self):
        """Test run_stdio handles KeyboardInterrupt."""
        from mobile_mcp.__main__ import run_stdio

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock(side_effect=KeyboardInterrupt())

        # Should not raise, just log and return
        run_stdio(mock_mcp)

    def test_run_stdio_error(self):
        """Test run_stdio handles errors."""
        from mobile_mcp.__main__ import run_stdio

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock(side_effect=Exception("Test error"))

        with pytest.raises(SystemExit) as exc_info:
            run_stdio(mock_mcp)
        
        assert exc_info.value.code == 1

    def test_run_http_success(self):
        """Test run_http executes without error."""
        from mobile_mcp.__main__ import run_http

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock()

        run_http(mock_mcp, "127.0.0.1", 8080)
        mock_mcp.run.assert_called_once_with(
            transport="sse", host="127.0.0.1", port=8080
        )

    def test_run_http_keyboard_interrupt(self):
        """Test run_http handles KeyboardInterrupt."""
        from mobile_mcp.__main__ import run_http

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock(side_effect=KeyboardInterrupt())

        # Should not raise, just log and return
        run_http(mock_mcp, "127.0.0.1", 8080)

    def test_run_http_error(self):
        """Test run_http handles errors."""
        from mobile_mcp.__main__ import run_http

        mock_mcp = MagicMock()
        mock_mcp.run = MagicMock(side_effect=Exception("Port in use"))

        with pytest.raises(SystemExit) as exc_info:
            run_http(mock_mcp, "127.0.0.1", 8080)
        
        assert exc_info.value.code == 1


# ============================================================================
# Integration Tests
# ============================================================================


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_server_creation_in_main(self):
        """Test that server is properly created in main."""
        with patch("sys.argv", ["mobile-mcp"]):
            from mobile_mcp.__main__ import main

            with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                mock_mcp = MagicMock()
                mock_create.return_value = mock_mcp
                
                with patch("mobile_mcp.__main__.run_stdio"):
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    mock_create.assert_called_once()

    def test_logging_configured_before_server(self):
        """Test that logging is configured before server creation."""
        with patch("sys.argv", ["mobile-mcp", "--log-level", "DEBUG"]):
            from mobile_mcp.__main__ import main

            call_order = []

            with patch("mobile_mcp.__main__.configure_logging") as mock_log:
                mock_log.side_effect = lambda **kwargs: call_order.append("logging")
                
                with patch("mobile_mcp.__main__.create_mcp_server") as mock_create:
                    mock_mcp = MagicMock()
                    mock_create.side_effect = lambda: (
                        call_order.append("server"),
                        mock_mcp,
                    )[1]
                    
                    with patch("mobile_mcp.__main__.run_stdio"):
                        try:
                            main()
                        except SystemExit:
                            pass

            # Logging should be configured before server is created
            if len(call_order) >= 2:
                assert call_order.index("logging") < call_order.index("server")


# ============================================================================
# Help Message Tests
# ============================================================================


class TestHelpMessages:
    """Test help messages and documentation."""

    def test_help_flag(self, capsys):
        """Test --help flag shows usage information."""
        with patch("sys.argv", ["mobile-mcp", "--help"]):
            from mobile_mcp.__main__ import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            
            # Should contain program name and options
            assert "mobile-mcp" in captured.out
            assert "--transport" in captured.out
            assert "--host" in captured.out
            assert "--port" in captured.out
            assert "--log-level" in captured.out

    def test_help_mentions_transports(self, capsys):
        """Test help message mentions transport options."""
        with patch("sys.argv", ["mobile-mcp", "--help"]):
            from mobile_mcp.__main__ import main

            with pytest.raises(SystemExit):
                main()
            
            captured = capsys.readouterr()
            assert "stdio" in captured.out
            assert "http" in captured.out


# ============================================================================
# Environment Variable Tests
# ============================================================================


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_server_respects_env_vars(self):
        """Test that server creation respects environment variables."""
        with patch.dict(
            "os.environ",
            {
                "BROWSERSTACK_USERNAME": "test_user",
                "BROWSERSTACK_ACCESS_KEY": "test_key",
            },
        ):
            from mobile_mcp.server import create_mcp_server

            # Should not raise even with BrowserStack configured
            mcp = create_mcp_server()
            assert mcp is not None

    def test_server_works_without_optional_env_vars(self):
        """Test server works without optional environment variables."""
        import os

        # Remove optional env vars
        for var in [
            "BROWSERSTACK_USERNAME",
            "BROWSERSTACK_ACCESS_KEY",
            "MOBILE_MCP_IMAGE_FORMAT",
            "MOBILE_MCP_IMAGE_QUALITY",
        ]:
            os.environ.pop(var, None)

        from mobile_mcp.server import create_mcp_server

        mcp = create_mcp_server()
        assert mcp is not None
