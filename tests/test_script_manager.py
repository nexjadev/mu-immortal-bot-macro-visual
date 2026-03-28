"""test_script_manager.py — Unit tests for core.script_manager.

Run with:
    python -m unittest tests.test_script_manager -v
from the project root (D:\\mu-immortal-bot-macro-visual).
"""

import json
import unittest
from pathlib import Path

from core.script_manager import ScriptManager, ScriptValidationError, ScriptNotFoundError


class TestScriptManager(unittest.TestCase):
    """Tests for ScriptManager load/save/validate and profile CRUD."""

    def setUp(self) -> None:
        self.sm = ScriptManager()
        self.tmp = Path("tests/_tmp_script.json")

    def tearDown(self) -> None:
        self.tmp.unlink(missing_ok=True)
        Path("config/profiles.json").unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_script(self) -> dict:
        """Return a minimal valid script dict for testing."""
        return {
            "meta": {
                "name": "TestScript",
                "resolution": {"width": 1280, "height": 720},
                "created_at": "",
                "version": "1.0",
            },
            "emulator": {
                "host": "127.0.0.1",
                "port": 5555,
            },
            "actions": [
                {
                    "id": "act1",
                    "name": "Click",
                    "enabled": True,
                    "roi": {"x": 0, "y": 0, "w": 100, "h": 50},
                    "click_type": "single",
                    "delay_before": 100,
                    "delay_after": 200,
                    "on_error": "stop",
                }
            ],
            "cycle_delay": 500,
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_save_and_load(self) -> None:
        """save() persists the script; load() restores it correctly."""
        script = self._make_script()
        self.sm.save(script, str(self.tmp))
        result = self.sm.load(str(self.tmp))
        self.assertEqual(result["meta"]["name"], "TestScript")
        self.assertEqual(result["actions"][0]["id"], "act1")

    def test_validate_ok(self) -> None:
        """validate() does not raise for a fully valid script."""
        self.sm.validate(self._make_script())

    def test_validate_empty_actions_allowed(self) -> None:
        """validate() acepta actions vacío (script guardado antes de dibujar ROIs)."""
        script = self._make_script()
        script["actions"] = []
        self.sm.validate(script)  # no debe lanzar

    def test_validate_actions_not_list_raises(self) -> None:
        """validate() rechaza actions que no sea lista."""
        script = self._make_script()
        script["actions"] = "no_es_lista"
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(script)
        self.assertEqual(ctx.exception.field, "actions")

    def test_validate_resolution_zero_zero(self) -> None:
        """validate() acepta resolution 0x0 (scripts creados desde la UI sin referencia)."""
        script = self._make_script()
        script["meta"]["resolution"] = {"width": 0, "height": 0}
        # No debe lanzar excepción
        self.sm.validate(script)

    def test_validate_resolution_negative_raises(self) -> None:
        """validate() rechaza resoluciones negativas."""
        script = self._make_script()
        script["meta"]["resolution"]["width"] = -1
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(script)
        self.assertEqual(ctx.exception.field, "meta.resolution.width")

    def test_validate_missing_field(self) -> None:
        """validate() raises ScriptValidationError when a top-level key is absent."""
        script = self._make_script()
        del script["actions"]
        with self.assertRaises(ScriptValidationError):
            self.sm.validate(script)

    def test_validate_invalid_roi(self) -> None:
        """validate() raises ScriptValidationError with correct field for roi.w == 0."""
        script = self._make_script()
        script["actions"][0]["roi"]["w"] = 0
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(script)
        self.assertEqual(ctx.exception.field, "actions[0].roi.w")

    def test_validate_invalid_click_type(self) -> None:
        """validate() raises ScriptValidationError with correct field for bad click_type."""
        script = self._make_script()
        script["actions"][0]["click_type"] = "triple"
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(script)
        self.assertEqual(ctx.exception.field, "actions[0].click_type")

    def test_load_not_found(self) -> None:
        """load() raises ScriptNotFoundError for a nonexistent path."""
        with self.assertRaises(ScriptNotFoundError):
            self.sm.load("nonexistent/path.json")

    def test_save_updates_created_at(self) -> None:
        """save() sets a non-empty meta.created_at timestamp."""
        script = self._make_script()
        self.sm.save(script, str(self.tmp))
        result = self.sm.load(str(self.tmp))
        self.assertTrue(len(result["meta"]["created_at"]) > 0)

    def test_profiles_crud(self) -> None:
        """save_profile / load_profiles / delete_profile work end-to-end."""
        # Create
        self.sm.save_profile(
            {"name": "emu1", "host": "127.0.0.1", "port": 5555}
        )
        profiles = self.sm.load_profiles()
        self.assertEqual(len(profiles), 1)

        # Update in-place (same name)
        self.sm.save_profile(
            {"name": "emu1", "host": "10.0.0.1", "port": 5556}
        )
        profiles = self.sm.load_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["host"], "10.0.0.1")

        # Delete
        self.sm.delete_profile("emu1")
        profiles = self.sm.load_profiles()
        self.assertEqual(len(profiles), 0)


if __name__ == "__main__":
    unittest.main()
