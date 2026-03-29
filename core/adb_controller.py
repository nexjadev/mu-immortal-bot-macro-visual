"""
core/adb_controller.py
======================
Single point of contact with ADB for the mu-immortal-bot-macro-visual project.
Provides device connection, input simulation, and screenshot capture via ADB.
"""

import io
import logging
import re
import subprocess

from PIL import Image


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ADBCommandError(Exception):
    """Raised when an ADB command returns a non-zero exit code or fails."""

    def __init__(self, command: str, stderr: str) -> None:
        self.command = command
        self.stderr = stderr
        super().__init__(f"ADB command failed: {command!r} — {stderr.strip()}")


class ADBConnectionError(Exception):
    """Raised when the ADB device is not available or the connection fails."""
    pass


# ---------------------------------------------------------------------------
# ADBController
# ---------------------------------------------------------------------------

class ADBController:
    """
    Wraps all ADB interactions for a single emulator device identified by
    host:port (e.g. 127.0.0.1:5555).

    Usage::

        adb = ADBController("127.0.0.1", 5555)
        adb.connect()
        width, height = adb.get_resolution()
        adb.tap(640, 360)
        img = adb.screenshot()
        adb.disconnect()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5555) -> None:
        """
        Initialise the controller.

        Args:
            host: IP address of the ADB device / emulator host.
            port: TCP port on which the ADB daemon is listening.
        """
        self.host = host
        self.port = port
        self._connected: bool = False
        self._logger = logging.getLogger("bot.adb")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run(self, *args: str, timeout: int = 5) -> str:
        """
        Execute an ADB shell command against the configured device and return
        stdout as a decoded, stripped string.

        Args:
            *args: ADB sub-command and its arguments (e.g. "shell", "wm", "size").
            timeout: Maximum seconds to wait for the subprocess.

        Returns:
            Decoded stdout of the command.

        Raises:
            ADBCommandError: If the command exits with a non-zero return code
                             or the subprocess times out.
        """
        cmd = ["adb", "-s", f"{self.host}:{self.port}", *args]
        self._logger.debug("ADB: %s", " ".join(str(a) for a in cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ADBCommandError(
                " ".join(str(a) for a in cmd),
                f"Command timed out after {timeout}s",
            )
        except FileNotFoundError:
            raise ADBConnectionError("ADB executable not found in PATH")

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise ADBCommandError(" ".join(str(a) for a in cmd), stderr)

        return result.stdout.decode(errors="replace").strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """
        Connect to the device using ``adb connect host:port``.

        Sets the internal ``_connected`` flag to ``True`` on success.

        Raises:
            ADBConnectionError: If ADB reports it cannot reach the device.
        """
        cmd = ["adb", "connect", f"{self.host}:{self.port}"]
        self._logger.debug("ADB: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
        except FileNotFoundError:
            raise ADBConnectionError("ADB executable not found in PATH")

        out = result.stdout.decode(errors="replace").strip().lower()

        if "unable to connect" in out or "failed" in out or result.returncode != 0:
            raise ADBConnectionError(
                f"Cannot connect to {self.host}:{self.port} — {out}"
            )

        # Verify the device is actually an ADB daemon (not just an open TCP port).
        if not self.is_connected():
            raise ADBConnectionError(
                f"Port {self.host}:{self.port} responded but is not an ADB device"
            )

        self._connected = True
        self._logger.info("Connected to %s:%s", self.host, self.port)

    def is_connected(self) -> bool:
        """
        Check whether the device is currently reachable.

        Performs a live ``get-state`` query rather than relying solely on
        the cached ``_connected`` flag.

        Returns:
            ``True`` if the device responds with ``device``, ``False`` otherwise.
        """
        try:
            out = self._run("get-state")
            return out == "device"
        except (ADBCommandError, ADBConnectionError, subprocess.TimeoutExpired):
            return False

    def get_resolution(self) -> tuple[int, int]:
        """
        Query the physical display resolution of the device.

        Returns:
            ``(width, height)`` as a tuple of integers.

        Raises:
            ADBCommandError: If the command fails or the output cannot be parsed.
        """
        out = self._run("shell", "wm", "size")
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
        if not match:
            raise ADBCommandError("shell wm size", f"Unexpected output: {out}")

        width, height = int(match.group(1)), int(match.group(2))
        self._logger.info("Device resolution: %dx%d", width, height)
        return (width, height)

    def tap(self, x: int, y: int) -> None:
        """
        Send a single tap event to the given screen coordinates.

        Args:
            x: Horizontal coordinate in pixels.
            y: Vertical coordinate in pixels.

        Raises:
            ADBCommandError: If the underlying ADB command fails.
        """
        self._run("shell", "input", "tap", str(x), str(y))
        self._logger.debug("tap(%d, %d)", x, y)

    def double_tap(self, x: int, y: int) -> None:
        """
        Send two consecutive tap events to the given screen coordinates.

        Args:
            x: Horizontal coordinate in pixels.
            y: Vertical coordinate in pixels.

        Raises:
            ADBCommandError: If either underlying ADB command fails.
        """
        self._run("shell", "input", "tap", str(x), str(y))
        self._run("shell", "input", "tap", str(x), str(y))
        self._logger.debug("double_tap(%d, %d)", x, y)

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """
        Simulate a long-press by issuing a zero-distance swipe with a duration.

        Args:
            x: Horizontal coordinate in pixels.
            y: Vertical coordinate in pixels.
            duration_ms: Press duration in milliseconds (default 1000).

        Raises:
            ADBCommandError: If the underlying ADB command fails.
        """
        self._run(
            "shell", "input", "swipe",
            str(x), str(y), str(x), str(y), str(duration_ms),
        )
        self._logger.debug("long_press(%d, %d, %dms)", x, y, duration_ms)

    def screenshot(self) -> Image.Image:
        """
        Capture a screenshot from the device and return it as a Pillow Image.

        Uses ``adb exec-out screencap -p`` for direct binary transfer without
        intermediate file storage on the device.

        Returns:
            A ``PIL.Image.Image`` object representing the current screen.

        Raises:
            ADBCommandError: If the command exits with a non-zero code or the
                             output is empty / not a valid image.
        """
        cmd = ["adb", "-s", f"{self.host}:{self.port}", "exec-out", "screencap", "-p"]
        self._logger.debug("ADB: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            raise ADBCommandError(" ".join(cmd), "screencap timed out after 10s")
        except FileNotFoundError:
            raise ADBConnectionError("ADB executable not found in PATH")

        if result.returncode != 0:
            raise ADBCommandError(
                " ".join(cmd),
                result.stderr.decode(errors="replace").strip(),
            )

        self._logger.debug("Screenshot captured (%d bytes)", len(result.stdout))
        return Image.open(io.BytesIO(result.stdout))

    def disconnect(self) -> None:
        """
        Disconnect from the device and reset the internal connection state.

        Sends ``adb disconnect host:port`` when a device target is configured.
        Errors during disconnect are intentionally suppressed — the internal
        state is always reset to ``False``.
        """
        cmd = ["adb", "disconnect", f"{self.host}:{self.port}"]
        self._logger.debug("ADB: %s", " ".join(cmd))

        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except Exception:
            pass  # best-effort; state is reset regardless

        self._connected = False
        self._logger.info("Disconnected from %s:%s", self.host, self.port)
