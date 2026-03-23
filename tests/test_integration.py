"""
tests/test_integration.py
=========================
Integration tests for core/orchestrator.py.

All external I/O (ADB subprocess calls, file system access, log file
creation) is replaced with MagicMock instances so the tests run in any
environment without a connected device or real script files.
"""

import threading
import time
import unittest
from unittest.mock import MagicMock

from core.adb_controller import ADBConnectionError
from core.orchestrator import Orchestrator, ResolutionMismatchError


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests that exercise the Orchestrator end-to-end."""

    # ------------------------------------------------------------------
    # Setup / helpers
    # ------------------------------------------------------------------

    def setUp(self) -> None:
        """Create a fresh Orchestrator and patch all I/O-bound sub-systems."""
        self.orc = Orchestrator()

        # Replace real sub-systems with mocks to avoid file/ADB I/O.
        self.orc._adb = MagicMock()
        self.orc._logger = MagicMock()
        self.orc._script_manager = MagicMock()

        # Re-create the engine with the mocked adb and logger so that
        # BotEngine.start() does not attempt real ADB calls.
        from core.bot_engine import BotEngine
        self.orc._engine = BotEngine(self.orc._adb, self.orc._logger)

        # Capture emitted states for assertions.
        self.states: list[str] = []
        self.orc.on_state_change = self.states.append

    def _make_script(self, width: int = 1280, height: int = 720) -> dict:
        """Return a minimal valid script dict for the given resolution."""
        return {
            "meta": {
                "name": "IntegTest",
                "resolution": {"width": width, "height": height},
                "created_at": "",
                "version": "1.0",
            },
            "emulator": {
                "host": "127.0.0.1",
                "port": 5555,
                "window_title": "",
            },
            "actions": [
                {
                    "id": "a1",
                    "name": "Click",
                    "enabled": True,
                    "roi": {"x": 0, "y": 0, "w": 1, "h": 1},
                    "click_type": "single",
                    "delay_before": 0,
                    "delay_after": 0,
                    "on_error": "stop",
                }
            ],
            "cycle_delay": 0,
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_connect_success_state(self) -> None:
        """Successful connect emits 'connecting' then 'connected'."""
        self.orc._adb.connect = MagicMock()
        self.orc.connect("127.0.0.1", 5555, "")
        self.assertIn("connecting", self.states)
        self.assertIn("connected", self.states)

    def test_connect_failure_state(self) -> None:
        """ADBConnectionError causes the 'error' state to be emitted."""
        self.orc._adb.connect.side_effect = ADBConnectionError("offline")
        self.orc.connect("127.0.0.1", 5555, "")
        self.assertIn("error", self.states)

    def test_load_script_valid(self) -> None:
        """load_script stores the returned dict in self.orc._script."""
        self.orc._script_manager.load.return_value = self._make_script()
        self.orc.load_script("fake.json")
        self.assertIsNotNone(self.orc._script)

    def test_validate_resolution_ok(self) -> None:
        """validate_resolution does not raise when resolutions match."""
        self.orc._script = self._make_script(1280, 720)
        self.orc._adb.get_resolution.return_value = (1280, 720)
        # Should complete without raising.
        self.orc.validate_resolution()

    def test_validate_resolution_mismatch(self) -> None:
        """validate_resolution raises ResolutionMismatchError on mismatch."""
        self.orc._script = self._make_script(1280, 720)
        self.orc._adb.get_resolution.return_value = (1920, 1080)
        with self.assertRaises(ResolutionMismatchError):
            self.orc.validate_resolution()

    def test_start_and_stop_bot(self) -> None:
        """start_bot emits 'running'; stop_bot emits 'stopped'."""
        self.orc._script = self._make_script()
        self.orc._adb.get_resolution.return_value = (1280, 720)
        self.orc._adb.tap = MagicMock()

        self.orc.start_bot(cycles=0)
        time.sleep(0.05)  # allow the daemon thread to start
        self.orc.stop_bot()

        self.assertIn("running", self.states)
        self.assertIn("stopped", self.states)


if __name__ == "__main__":
    unittest.main()
