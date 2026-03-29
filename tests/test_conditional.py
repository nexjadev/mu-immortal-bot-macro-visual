"""
tests/test_conditional.py
=========================
Tests for the "conditional" action type.

Two test classes:
  - TestBotEngineConditional  (mocked detector/ADB, no real device)
  - TestScriptManagerConditional  (real ScriptManager validation)

Run with:
    python -m unittest tests.test_conditional -v
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Mock PIL before any core imports.
if "PIL" not in sys.modules:
    _pil_mock = MagicMock()
    sys.modules["PIL"] = _pil_mock
    sys.modules["PIL.Image"] = _pil_mock.Image

from core.bot_engine import BotEngine
from core.script_manager import ScriptManager, ScriptValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conditional_action(
    action_id: str = "cond01",
    name: str = "Condicional",
    on_found: str = "next",
    on_found_target_id=None,
    on_not_found: str = "stop",
    on_not_found_target_id=None,
    template_path: str = "assets/templates/tpl_test.png",
) -> dict:
    return {
        "id": action_id,
        "name": name,
        "enabled": True,
        "roi": {"x": 0, "y": 0, "w": 100, "h": 50},
        "click_type": "conditional",
        "template_path": template_path,
        "threshold": 0.8,
        "max_retries": 0,
        "retry_delay_ms": 0,
        "on_found": on_found,
        "on_found_target_id": on_found_target_id,
        "on_not_found": on_not_found,
        "on_not_found_target_id": on_not_found_target_id,
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "stop",
    }


def _make_click_action(action_id: str, name: str) -> dict:
    return {
        "id": action_id,
        "name": name,
        "enabled": True,
        "roi": {"x": 0, "y": 0, "w": 1, "h": 1},
        "click_type": "single",
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "stop",
    }


def _make_full_script(actions: list) -> dict:
    return {
        "meta": {
            "name": "ConditionalTest",
            "resolution": {"width": 1280, "height": 720},
            "created_at": "",
            "version": "1.0",
        },
        "emulator": {"host": "127.0.0.1", "port": 5555},
        "actions": actions,
        "cycle_delay": 0,
    }


# ---------------------------------------------------------------------------
# 1. BotEngine conditional execution
# ---------------------------------------------------------------------------

class TestBotEngineConditional(unittest.TestCase):
    """Tests for the conditional branch logic in BotEngine."""

    def setUp(self) -> None:
        self.adb = MagicMock()
        self.logger = MagicMock()
        self.detector = MagicMock()
        self.engine = BotEngine(self.adb, self.logger, detector=self.detector)
        self.detector.get_frame.return_value = MagicMock()

    def _run_once(self, actions: list) -> None:
        """Load actions and run exactly 1 cycle."""
        self.engine.load_actions(actions)
        self.engine.start(cycles=1)

    # ------------------------------------------------------------------
    # on_found = "next"
    # ------------------------------------------------------------------

    def test_found_next_advances_sequentially(self) -> None:
        """If found and on_found=next, execution continues to the next action."""
        self.detector.find_template.return_value = True
        click = _make_click_action("a2", "Click")
        cond = _make_conditional_action(
            "c1", on_found="next", on_not_found="stop"
        )
        self._run_once([cond, click])
        self.adb.tap.assert_called_once()

    # ------------------------------------------------------------------
    # on_not_found = "next"
    # ------------------------------------------------------------------

    def test_not_found_next_advances_sequentially(self) -> None:
        """If not found and on_not_found=next, execution continues to next action."""
        self.detector.find_template.return_value = False
        click = _make_click_action("a2", "Click")
        cond = _make_conditional_action(
            "c1", on_found="stop", on_not_found="next"
        )
        self._run_once([cond, click])
        self.adb.tap.assert_called_once()

    # ------------------------------------------------------------------
    # on_found = "stop"
    # ------------------------------------------------------------------

    def test_found_stop_halts_bot(self) -> None:
        """If found and on_found=stop, the bot stops and the next action is skipped."""
        self.detector.find_template.return_value = True
        click = _make_click_action("a2", "Click")
        cond = _make_conditional_action(
            "c1", on_found="stop", on_not_found="next"
        )
        self._run_once([cond, click])
        self.adb.tap.assert_not_called()

    # ------------------------------------------------------------------
    # on_not_found = "stop"
    # ------------------------------------------------------------------

    def test_not_found_stop_halts_bot(self) -> None:
        """If not found and on_not_found=stop, the bot stops and the next action is skipped."""
        self.detector.find_template.return_value = False
        click = _make_click_action("a2", "Click")
        cond = _make_conditional_action(
            "c1", on_found="next", on_not_found="stop"
        )
        self._run_once([cond, click])
        self.adb.tap.assert_not_called()

    # ------------------------------------------------------------------
    # on_found = "goto"
    # ------------------------------------------------------------------

    def test_found_goto_jumps_to_target(self) -> None:
        """If found and on_found=goto, execution jumps to the target action."""
        self.detector.find_template.return_value = True
        skipped = _make_click_action("skip", "Skipped")
        target = _make_click_action("tgt", "Target")
        cond = _make_conditional_action(
            "c1",
            on_found="goto",
            on_found_target_id="tgt",
            on_not_found="stop",
        )
        # Order: conditional → skipped → target
        # Goto jumps over "skipped" directly to "target".
        self._run_once([cond, skipped, target])
        # Only "target" should have been tapped, not "skipped".
        self.assertEqual(self.adb.tap.call_count, 1)

    # ------------------------------------------------------------------
    # on_not_found = "goto"
    # ------------------------------------------------------------------

    def test_not_found_goto_jumps_to_target(self) -> None:
        """If not found and on_not_found=goto, execution jumps to the target action."""
        self.detector.find_template.return_value = False
        skipped = _make_click_action("skip", "Skipped")
        target = _make_click_action("tgt", "Target")
        cond = _make_conditional_action(
            "c1",
            on_found="stop",
            on_not_found="goto",
            on_not_found_target_id="tgt",
        )
        self._run_once([cond, skipped, target])
        self.assertEqual(self.adb.tap.call_count, 1)

    # ------------------------------------------------------------------
    # goto with invalid (stale) target id
    # ------------------------------------------------------------------

    def test_found_goto_invalid_target_falls_through(self) -> None:
        """If goto target id does not exist, engine logs a warning and advances normally."""
        self.detector.find_template.return_value = True
        click = _make_click_action("a2", "Click")
        cond = _make_conditional_action(
            "c1",
            on_found="goto",
            on_found_target_id="nonexistent_id",
            on_not_found="stop",
        )
        self._run_once([cond, click])
        # Falls through to next action.
        self.adb.tap.assert_called_once()
        # A warning must have been logged.
        self.logger.warn.assert_called()

    # ------------------------------------------------------------------
    # goto backward (loop-like)
    # ------------------------------------------------------------------

    def test_goto_backward_executes_target_action(self) -> None:
        """A goto pointing backward causes the target action to execute."""
        call_count = {"n": 0}

        def tap_side_effect(x, y):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                # Stop after the target has been reached once.
                self.engine.stop()

        self.adb.tap.side_effect = tap_side_effect
        self.detector.find_template.return_value = True

        target = _make_click_action("first", "First")
        cond = _make_conditional_action(
            "c1",
            on_found="goto",
            on_found_target_id="first",
            on_not_found="stop",
        )
        self.engine.load_actions([target, cond])
        self.engine.start(cycles=0)
        self.assertGreaterEqual(call_count["n"], 1)

    # ------------------------------------------------------------------
    # conditional action does NOT produce a tap
    # ------------------------------------------------------------------

    def test_conditional_does_not_tap(self) -> None:
        """A conditional action must never call adb.tap regardless of the result."""
        for found_result in (True, False):
            self.adb.reset_mock()
            self.detector.find_template.return_value = found_result
            cond = _make_conditional_action(
                "c1", on_found="next", on_not_found="next"
            )
            self._run_once([cond])
            self.adb.tap.assert_not_called()


# ---------------------------------------------------------------------------
# 2. ScriptManager validation for conditional
# ---------------------------------------------------------------------------

class TestScriptManagerConditional(unittest.TestCase):
    """Tests for ScriptManager validation of the conditional action type."""

    def setUp(self) -> None:
        self.sm = ScriptManager()
        self.tmp = tempfile.mkdtemp()

    def _save_and_load(self, script: dict) -> dict:
        path = str(Path(self.tmp) / "cond_test.json")
        self.sm.save(script, path)
        return self.sm.load(path)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_valid_conditional_next_next(self) -> None:
        """Full conditional with on_found=next, on_not_found=next passes validation."""
        action = _make_conditional_action(
            on_found="next", on_not_found="next"
        )
        script = _make_full_script([action])
        loaded = self._save_and_load(script)
        self.assertEqual(loaded["actions"][0]["click_type"], "conditional")

    def test_valid_conditional_goto(self) -> None:
        """Conditional with on_found=goto and a target id passes validation."""
        action = _make_conditional_action(
            on_found="goto",
            on_found_target_id="abc12345",
            on_not_found="stop",
        )
        script = _make_full_script([action])
        loaded = self._save_and_load(script)
        self.assertEqual(loaded["actions"][0]["on_found_target_id"], "abc12345")

    # ------------------------------------------------------------------
    # Missing / invalid on_found
    # ------------------------------------------------------------------

    def test_missing_on_found_raises(self) -> None:
        action = _make_conditional_action()
        del action["on_found"]
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    def test_invalid_on_found_value_raises(self) -> None:
        action = _make_conditional_action(on_found="continue")
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    # ------------------------------------------------------------------
    # Missing / invalid on_not_found
    # ------------------------------------------------------------------

    def test_missing_on_not_found_raises(self) -> None:
        action = _make_conditional_action()
        del action["on_not_found"]
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    def test_invalid_on_not_found_value_raises(self) -> None:
        action = _make_conditional_action(on_not_found="ignore")
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    # ------------------------------------------------------------------
    # goto requires target_id
    # ------------------------------------------------------------------

    def test_found_goto_without_target_id_raises(self) -> None:
        action = _make_conditional_action(
            on_found="goto", on_found_target_id=None
        )
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    def test_not_found_goto_without_target_id_raises(self) -> None:
        action = _make_conditional_action(
            on_found="next",
            on_not_found="goto",
            on_not_found_target_id=None,
        )
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    # ------------------------------------------------------------------
    # Missing template_path
    # ------------------------------------------------------------------

    def test_missing_template_path_raises(self) -> None:
        action = _make_conditional_action()
        del action["template_path"]
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(_make_full_script([action]))

    # ------------------------------------------------------------------
    # Roundtrip save/load preserves all fields
    # ------------------------------------------------------------------

    def test_roundtrip_preserves_all_conditional_fields(self) -> None:
        action = _make_conditional_action(
            on_found="goto",
            on_found_target_id="abc00001",
            on_not_found="stop",
        )
        script = _make_full_script([action])
        loaded = self._save_and_load(script)
        a = loaded["actions"][0]
        self.assertEqual(a["on_found"], "goto")
        self.assertEqual(a["on_found_target_id"], "abc00001")
        self.assertEqual(a["on_not_found"], "stop")
        self.assertIsNone(a["on_not_found_target_id"])
        self.assertEqual(a["threshold"], 0.8)
        self.assertEqual(a["max_retries"], 0)


if __name__ == "__main__":
    unittest.main()
