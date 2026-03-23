"""
tests/test_bot_engine.py
========================
Unit tests for core/bot_engine.py.

All ADB and logger calls are mocked so no real device is needed.
"""

import unittest
from unittest.mock import MagicMock

from core.adb_controller import ADBConnectionError
from core.bot_engine import BotEngine


class TestBotEngine(unittest.TestCase):
    """Tests for the BotEngine execution loop."""

    def setUp(self) -> None:
        self.adb = MagicMock()
        self.logger = MagicMock()
        self.engine = BotEngine(self.adb, self.logger)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_action(
        self,
        name: str = "A",
        click_type: str = "single",
        enabled: bool = True,
        on_error: str = "stop",
    ) -> dict:
        """Return a minimal, deterministic action dict for testing."""
        return {
            "id": name,
            "name": name,
            "enabled": enabled,
            # ROI with w=1 h=1 → randint(0, max(1-1,0)) = randint(0,0) = 0
            "roi": {"x": 0, "y": 0, "w": 1, "h": 1},
            "click_type": click_type,
            "delay_before": 0,
            "delay_after": 0,
            "on_error": on_error,
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_actions_executed_in_order(self) -> None:
        """Both enabled actions must be executed in declaration order."""
        action_a = self._make_action("A")
        action_b = self._make_action("B")
        self.engine.load_actions([action_a, action_b])
        self.engine.start(cycles=1)

        self.assertEqual(self.adb.tap.call_count, 2)
        self.assertEqual(self.logger.action.call_count, 2)

        calls = self.logger.action.call_args_list
        self.assertEqual(calls[0][0][0], "A")
        self.assertEqual(calls[1][0][0], "B")

    def test_disabled_action_skipped(self) -> None:
        """An action with enabled=False must not trigger any ADB call."""
        self.engine.load_actions([self._make_action(enabled=False)])
        self.engine.start(cycles=1)

        self.assertEqual(self.adb.tap.call_count, 0)

    def test_cycles_limit(self) -> None:
        """on_cycle_complete is called once per cycle; cycle numbers are 1-based."""
        call_count: list[int] = []
        self.engine.on_cycle_complete = lambda c: call_count.append(c)
        self.engine.load_actions([self._make_action()])
        self.engine.start(cycles=3)

        self.assertEqual(len(call_count), 3)
        self.assertEqual(call_count[-1], 3)

    def test_stop_interrupts_loop(self) -> None:
        """stop() called from on_cycle_complete halts an infinite loop after 1 cycle."""
        self.engine.on_cycle_complete = lambda c: self.engine.stop()
        self.engine.load_actions([self._make_action()])
        self.engine.start(cycles=0)  # infinite — relies on stop() to exit

        self.assertEqual(self.adb.tap.call_count, 1)

    def test_on_error_skip_continues(self) -> None:
        """
        When action A fails and on_error='skip', a WARNING is logged and the
        loop continues to execute action B.
        """
        action_a = self._make_action("A", on_error="skip")
        action_b = self._make_action("B", on_error="stop")
        self.adb.tap.side_effect = [Exception("fallo"), None]

        self.engine.load_actions([action_a, action_b])
        self.engine.start(cycles=1)

        self.assertTrue(self.logger.warn.called)
        self.assertEqual(self.adb.tap.call_count, 2)

    def test_adb_connection_error_stops_loop(self) -> None:
        """ADBConnectionError must stop the loop immediately and fire on_error."""
        self.adb.tap.side_effect = ADBConnectionError("offline")

        error_received: list[Exception] = []
        self.engine.on_error = lambda e: error_received.append(e)

        self.engine.load_actions([self._make_action()])
        self.engine.start(cycles=5)

        self.assertEqual(len(error_received), 1)
        self.assertIsInstance(error_received[0], ADBConnectionError)
        self.assertTrue(self.logger.error.called)

    def test_click_type_double_tap(self) -> None:
        """click_type='double' must call double_tap, not tap."""
        self.engine.load_actions([self._make_action(click_type="double")])
        self.engine.start(cycles=1)

        self.assertEqual(self.adb.double_tap.call_count, 1)
        self.assertEqual(self.adb.tap.call_count, 0)

    def test_click_type_long_press(self) -> None:
        """click_type='long_press' must call long_press."""
        self.engine.load_actions([self._make_action(click_type="long_press")])
        self.engine.start(cycles=1)

        self.assertEqual(self.adb.long_press.call_count, 1)


if __name__ == "__main__":
    unittest.main()
