"""Async subprocess utilities for Mobile MCP."""

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from mobile_mcp.logger import trace
from mobile_mcp.robots.base import ActionableError


@dataclass
class CommandResult:
    """Result of a subprocess command."""

    returncode: int
    stdout: str | None
    stderr: str | None


def run_command_sync(
    cmd: list[str],
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: int = 30,
    check: bool = False,
) -> CommandResult:
    """Run a command synchronously and return the result.

    Args:
        cmd: Command as a list of strings.
        cwd: Working directory.
        env: Environment variables (merged with current env).
        timeout: Timeout in seconds.
        check: If True, raise on non-zero exit code.

    Returns:
        CommandResult with returncode, stdout, and stderr.

    Raises:
        ActionableError: If command fails and check=True.
        subprocess.TimeoutExpired: If command times out.
    """
    cmd_str = " ".join(cmd)
    trace(f"Running command (sync): {cmd_str}")

    # Merge environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=full_env,
            timeout=timeout,
        )

        if check and result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
            raise ActionableError(f"Command failed: {cmd_str}\n{error_msg}")

        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    except subprocess.TimeoutExpired:
        raise ActionableError(f"Command timed out after {timeout}s: {cmd_str}")


async def run_command(
    *args: str,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = True,
) -> tuple[str, str]:
    """Run a command asynchronously and return stdout/stderr.

    Args:
        *args: Command and arguments.
        cwd: Working directory.
        env: Environment variables (merged with current env).
        timeout: Timeout in seconds.
        check: If True, raise on non-zero exit code.

    Returns:
        Tuple of (stdout, stderr) as strings.

    Raises:
        ActionableError: If command fails and check=True.
        asyncio.TimeoutError: If command times out.
    """
    cmd_str = " ".join(args)
    trace(f"Running command: {cmd_str}")

    # Merge environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=full_env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ActionableError(f"Command timed out after {timeout}s: {cmd_str}")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if check and process.returncode != 0:
        error_msg = stderr.strip() or stdout.strip() or f"Exit code {process.returncode}"
        raise ActionableError(f"Command failed: {cmd_str}\n{error_msg}")

    return stdout, stderr


async def run_command_raw(
    *args: str,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = True,
) -> bytes:
    """Run a command and return raw stdout bytes.

    Useful for binary output like screenshots.

    Args:
        *args: Command and arguments.
        cwd: Working directory.
        env: Environment variables.
        timeout: Timeout in seconds.
        check: If True, raise on non-zero exit code.

    Returns:
        Raw stdout bytes.
    """
    cmd_str = " ".join(args)
    trace(f"Running command (raw): {cmd_str}")

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=full_env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ActionableError(f"Command timed out after {timeout}s: {cmd_str}")

    if check and process.returncode != 0:
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        raise ActionableError(f"Command failed: {cmd_str}\n{stderr}")

    return stdout_bytes


def find_executable(name: str, env_var: Optional[str] = None) -> Optional[str]:
    """Find an executable by name or environment variable.

    Args:
        name: The executable name.
        env_var: Optional environment variable that may contain the path.

    Returns:
        Full path to the executable, or None if not found.
    """
    # Check environment variable first
    if env_var:
        path = os.environ.get(env_var)
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # Check if it's in PATH
    return shutil.which(name)


def get_adb_path() -> str:
    """Get the path to the adb executable.

    Returns:
        Path to adb.

    Raises:
        ActionableError: If adb is not found.
    """
    # Check ANDROID_HOME first
    android_home = os.environ.get("ANDROID_HOME")
    if android_home:
        adb_path = os.path.join(android_home, "platform-tools", "adb")
        if os.path.isfile(adb_path) and os.access(adb_path, os.X_OK):
            return adb_path

    # Check PATH
    adb = shutil.which("adb")
    if adb:
        return adb

    raise ActionableError(
        "adb not found. Please install Android SDK Platform Tools and ensure "
        "adb is in PATH, or set ANDROID_HOME environment variable."
    )


def get_go_ios_path() -> str:
    """Get the path to the go-ios executable.

    Returns:
        Path to go-ios (ios command).

    Raises:
        ActionableError: If go-ios is not found.
    """
    # Check environment variable
    go_ios_path = os.environ.get("GO_IOS_PATH")
    if go_ios_path and os.path.isfile(go_ios_path) and os.access(go_ios_path, os.X_OK):
        return go_ios_path

    # Check PATH
    ios_cmd = shutil.which("ios")
    if ios_cmd:
        return ios_cmd

    raise ActionableError(
        "go-ios not found. Please install go-ios (https://github.com/danielpaulus/go-ios) "
        "and ensure 'ios' command is in PATH, or set GO_IOS_PATH environment variable."
    )


def get_mobilecli_path() -> Optional[str]:
    """Get the path to the mobilecli executable.

    Returns:
        Path to mobilecli, or None if not found.
    """
    # Check environment variable
    mobilecli_path = os.environ.get("MOBILECLI_PATH")
    if mobilecli_path and os.path.isfile(mobilecli_path) and os.access(mobilecli_path, os.X_OK):
        return mobilecli_path

    # Check PATH
    return shutil.which("mobilecli")
