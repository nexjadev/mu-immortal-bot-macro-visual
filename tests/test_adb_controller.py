"""
tests/test_adb_controller.py
============================
Unit tests for core.adb_controller.ADBController.

All subprocess.run calls are patched via core.adb_controller.subprocess.run
so that no real ADB process is spawned during test execution.
"""

import io
import sys
import subprocess
import unittest
from unittest.mock import MagicMock, call, patch

try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PILImage = None
    _PIL_AVAILABLE = False
    # Mock PIL para que adb_controller pueda importarse sin Pillow instalado.
    _pil = MagicMock()
    sys.modules.setdefault("PIL", _pil)
    sys.modules.setdefault("PIL.Image", _pil.Image)

from core.adb_controller import ADBCommandError, ADBConnectionError, ADBController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    """Return a mock CompletedProcess representing a successful command."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = stderr
    return m


def _err(stderr: bytes = b"some error", returncode: int = 1) -> MagicMock:
    """Return a mock CompletedProcess representing a failed command."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = b""
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestADBController(unittest.TestCase):
    """Tests for ADBController using subprocess.run mocks."""

    def setUp(self) -> None:
        self.adb = ADBController("127.0.0.1", 5555)

    # ------------------------------------------------------------------
    # connect()
    # ------------------------------------------------------------------

    def test_connect_success(self) -> None:
        """connect() should set _connected=True when ADB reports success."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok(stdout=b"connected to 127.0.0.1:5555")
            self.adb.connect()
        self.assertTrue(self.adb._connected)

    def test_connect_failure_unable(self) -> None:
        """connect() should raise ADBConnectionError when ADB says 'unable to connect'."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok(stdout=b"unable to connect to 127.0.0.1:5555")
            with self.assertRaises(ADBConnectionError):
                self.adb.connect()

    # ------------------------------------------------------------------
    # ADBCommandError propagation
    # ------------------------------------------------------------------

    def test_command_error(self) -> None:
        """tap() should raise ADBCommandError whose .stderr matches the mock stderr."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _err(stderr=b"device offline")
            with self.assertRaises(ADBCommandError) as ctx:
                self.adb.tap(100, 200)
        self.assertEqual(ctx.exception.stderr, "device offline")

    # ------------------------------------------------------------------
    # tap()
    # ------------------------------------------------------------------

    def test_tap_command(self) -> None:
        """tap() should call ADB with shell input tap <x> <y> for the correct device."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            self.adb.tap(100, 200)

        cmd = mock_run.call_args[0][0]
        self.assertIn("-s", cmd)
        self.assertIn("127.0.0.1:5555", cmd)
        self.assertIn("shell", cmd)
        self.assertIn("input", cmd)
        self.assertIn("tap", cmd)
        self.assertIn("100", cmd)
        self.assertIn("200", cmd)

    # ------------------------------------------------------------------
    # double_tap()
    # ------------------------------------------------------------------

    def test_double_tap_calls_twice(self) -> None:
        """double_tap() should invoke subprocess.run exactly twice."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            self.adb.double_tap(50, 60)
        self.assertEqual(mock_run.call_count, 2)

    # ------------------------------------------------------------------
    # long_press()
    # ------------------------------------------------------------------

    def test_long_press_uses_swipe(self) -> None:
        """long_press() should issue an ADB swipe command with the correct duration."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            self.adb.long_press(10, 20, duration_ms=1500)

        cmd = mock_run.call_args[0][0]
        self.assertIn("swipe", cmd)
        self.assertIn("1500", cmd)

    # ------------------------------------------------------------------
    # get_resolution()
    # ------------------------------------------------------------------

    def test_get_resolution_parses_output(self) -> None:
        """get_resolution() should parse 'Physical size: WxH' and return (W, H)."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok(stdout=b"Physical size: 1280x720")
            result = self.adb.get_resolution()
        self.assertEqual(result, (1280, 720))

    # ------------------------------------------------------------------
    # is_connected()
    # ------------------------------------------------------------------

    def test_is_connected_true(self) -> None:
        """is_connected() should return True when the device state is 'device'."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok(stdout=b"device")
            self.assertTrue(self.adb.is_connected())

    def test_is_connected_false_on_error(self) -> None:
        """is_connected() should return False when the ADB command fails."""
        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _err()
            self.assertFalse(self.adb.is_connected())

    # ------------------------------------------------------------------
    # screenshot()
    # ------------------------------------------------------------------

    @unittest.skipUnless(_PIL_AVAILABLE, "Pillow no instalado — omitiendo test de screenshot")
    def test_screenshot_returns_pil_image(self) -> None:
        """screenshot() should return a PIL.Image.Image built from ADB binary output."""
        buf = io.BytesIO()
        _PILImage.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="PNG")
        png_bytes = buf.getvalue()

        with patch("core.adb_controller.subprocess.run") as mock_run:
            mock_run.return_value = _ok(stdout=png_bytes)
            result = self.adb.screenshot()

        self.assertIsInstance(result, _PILImage.Image)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
