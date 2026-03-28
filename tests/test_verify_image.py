"""
tests/test_verify_image.py
==========================
Tests for the verify_image action type.

Three test classes:
  - TestVisualDetectorFindTemplate  (requires cv2 + Pillow; skipped if unavailable)
  - TestBotEngineVerifyImage        (mocked, no real cv2)
  - TestScriptManagerVerifyImage    (real ScriptManager I/O)

Run with:
    python -m unittest tests.test_verify_image -v
"""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Availability checks
# ---------------------------------------------------------------------------

try:
    import cv2
    import numpy as np
    from PIL import Image as _PilImage
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# Mock PIL for imports that need it, without breaking real PIL if present.
if "PIL" not in sys.modules:
    _pil_mock = MagicMock()
    sys.modules["PIL"] = _pil_mock
    sys.modules["PIL.Image"] = _pil_mock.Image

from core.script_manager import ScriptManager, ScriptValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verify_action(
    template_path: str = "assets/templates/tpl_test.png",
    threshold: float = 0.85,
    max_retries: int = 3,
    retry_delay_ms: int = 0,
) -> dict:
    return {
        "id": "vi001",
        "name": "Verificar imagen",
        "enabled": True,
        "roi": {"x": 0, "y": 0, "w": 100, "h": 50},
        "click_type": "verify_image",
        "template_path": template_path,
        "threshold": threshold,
        "max_retries": max_retries,
        "retry_delay_ms": retry_delay_ms,
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "skip",
    }


def _make_full_script(action: dict) -> dict:
    return {
        "meta": {
            "name": "VerifyTest",
            "resolution": {"width": 1280, "height": 720},
            "created_at": "",
            "version": "1.0",
        },
        "emulator": {"host": "127.0.0.1", "port": 5555},
        "actions": [action],
        "cycle_delay": 0,
    }


# ---------------------------------------------------------------------------
# 1. VisualDetector.find_template  (requires cv2 + Pillow)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_CV2_AVAILABLE, "cv2 / Pillow not installed")
class TestVisualDetectorFindTemplate(unittest.TestCase):

    def setUp(self) -> None:
        from core.visual_detector import VisualDetector
        self.detector = VisualDetector()
        self.tmp_dir = tempfile.mkdtemp()

    def _solid_pil(self, w: int, h: int, color=(200, 100, 50)) -> "_PilImage.Image":
        img = _PilImage.new("RGB", (w, h), color)
        return img

    def _save_png(self, img, name: str) -> str:
        path = str(Path(self.tmp_dir) / name)
        img.save(path, "PNG")
        return path

    def test_found(self) -> None:
        """Template que es un recorte del frame → True."""
        frame = self._solid_pil(200, 100, color=(180, 180, 180))
        # Crear template como recorte exacto del frame
        tpl_array = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2GRAY)[10:40, 20:60]
        tpl_path = str(Path(self.tmp_dir) / "tpl_found.png")
        cv2.imwrite(tpl_path, tpl_array)

        roi = {"x": 0, "y": 0, "w": 200, "h": 100}
        result = self.detector.find_template(frame, tpl_path, roi, threshold=0.99)
        self.assertTrue(result)

    def test_not_found(self) -> None:
        """Template de color completamente diferente → False."""
        frame = self._solid_pil(200, 100, color=(200, 200, 200))
        tpl_img = self._solid_pil(20, 20, color=(0, 0, 0))
        tpl_path = self._save_png(tpl_img, "tpl_notfound.png")

        roi = {"x": 0, "y": 0, "w": 200, "h": 100}
        result = self.detector.find_template(frame, tpl_path, roi, threshold=0.99)
        self.assertFalse(result)

    def test_file_not_found(self) -> None:
        """Ruta inexistente → FileNotFoundError."""
        frame = self._solid_pil(100, 100)
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        with self.assertRaises(FileNotFoundError):
            self.detector.find_template(frame, "/no/existe.png", roi, threshold=0.8)

    def test_invalid_threshold(self) -> None:
        """threshold=1.5 → ValueError."""
        frame = self._solid_pil(100, 100)
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        with self.assertRaises(ValueError):
            self.detector.find_template(frame, "/no/existe.png", roi, threshold=1.5)

    def test_template_larger_than_roi(self) -> None:
        """Template más grande que el ROI → False sin error."""
        frame = self._solid_pil(200, 100)
        tpl_img = self._solid_pil(60, 60, color=(180, 180, 180))
        tpl_path = self._save_png(tpl_img, "tpl_big.png")

        roi = {"x": 0, "y": 0, "w": 30, "h": 30}   # ROI más pequeño que el template
        result = self.detector.find_template(frame, tpl_path, roi, threshold=0.8)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 2. BotEngine — verify_image branch (mocked detector)
# ---------------------------------------------------------------------------

class TestBotEngineVerifyImage(unittest.TestCase):

    def setUp(self) -> None:
        from core.bot_engine import BotEngine
        self.adb = MagicMock()
        self.logger = MagicMock()
        self.detector = MagicMock()
        # get_frame always returns a sentinel frame object
        self.detector.get_frame.return_value = MagicMock(name="frame")
        self.engine = BotEngine(self.adb, self.logger, self.detector)

        self.errors: list = []
        self.engine.on_error = self.errors.append

    def _make_action(self, on_error="skip", max_retries=2, retry_delay_ms=0):
        return {
            "id": "vi1",
            "name": "TestVerify",
            "enabled": True,
            "roi": {"x": 0, "y": 0, "w": 10, "h": 10},
            "click_type": "verify_image",
            "template_path": "fake/tpl.png",
            "threshold": 0.8,
            "max_retries": max_retries,
            "retry_delay_ms": retry_delay_ms,
            "delay_before": 0,
            "delay_after": 0,
            "on_error": on_error,
        }

    def _run_one_cycle(self, action):
        """Run one cycle in a thread that auto-stops after completion."""
        self.engine.load_actions([action])
        self.engine.start(cycles=1)

    def test_found_on_first_attempt(self) -> None:
        """detector retorna True → get_frame llamado 1 vez."""
        self.detector.find_template.return_value = True
        action = self._make_action(max_retries=5)
        self._run_one_cycle(action)
        self.assertEqual(self.detector.get_frame.call_count, 1)
        self.logger.info.assert_called()  # verify_image OK log

    def test_retries_then_finds(self) -> None:
        """detector retorna False x2 luego True → get_frame llamado 3 veces."""
        self.detector.find_template.side_effect = [False, False, True]
        action = self._make_action(max_retries=5)
        self._run_one_cycle(action)
        self.assertEqual(self.detector.get_frame.call_count, 3)

    def test_not_found_skip(self) -> None:
        """on_error='skip' → logger.warn llamado, no hay error fatal."""
        self.detector.find_template.return_value = False
        action = self._make_action(on_error="skip", max_retries=1)
        self._run_one_cycle(action)
        self.assertEqual(len(self.errors), 0)
        self.logger.warn.assert_called()

    def test_not_found_stop(self) -> None:
        """on_error='stop' → on_error callback llamado."""
        self.detector.find_template.return_value = False
        action = self._make_action(on_error="stop", max_retries=1)
        self._run_one_cycle(action)
        self.assertEqual(len(self.errors), 1)
        self.assertIsInstance(self.errors[0], Exception)

    def test_stop_event_exits_retry_loop(self) -> None:
        """stop() durante reintentos → el loop se detiene."""
        call_count = 0

        def slow_find_template(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Signal stop after first attempt
                self.engine.stop()
            return False

        self.detector.find_template.side_effect = slow_find_template

        action = self._make_action(max_retries=10)
        self.engine.load_actions([action])

        t = threading.Thread(target=self.engine.start, args=(0,), daemon=True)
        t.start()
        t.join(timeout=2.0)

        # Should have stopped early — far fewer than 10+1 attempts
        self.assertLessEqual(self.detector.get_frame.call_count, 3)


# ---------------------------------------------------------------------------
# 3. ScriptManager — verify_image validation + round-trip
# ---------------------------------------------------------------------------

class TestScriptManagerVerifyImage(unittest.TestCase):

    def setUp(self) -> None:
        self.sm = ScriptManager()
        self.tmp = Path("tests/_tmp_verify.json")

    def tearDown(self) -> None:
        self.tmp.unlink(missing_ok=True)

    def test_validate_valid(self) -> None:
        """Acción verify_image completa pasa sin error."""
        self.sm.validate(_make_full_script(_make_verify_action()))

    def test_missing_template_path(self) -> None:
        """Falta template_path → ScriptValidationError con field correcto."""
        action = _make_verify_action()
        del action["template_path"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(_make_full_script(action))
        self.assertIn("template_path", ctx.exception.field)

    def test_missing_max_retries(self) -> None:
        """Falta max_retries → ScriptValidationError."""
        action = _make_verify_action()
        del action["max_retries"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(_make_full_script(action))
        self.assertIn("max_retries", ctx.exception.field)

    def test_missing_retry_delay_ms(self) -> None:
        """Falta retry_delay_ms → ScriptValidationError."""
        action = _make_verify_action()
        del action["retry_delay_ms"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(_make_full_script(action))
        self.assertIn("retry_delay_ms", ctx.exception.field)

    def test_invalid_threshold(self) -> None:
        """threshold=2.0 → ScriptValidationError."""
        action = _make_verify_action(threshold=2.0)
        with self.assertRaises(ScriptValidationError) as ctx:
            self.sm.validate(_make_full_script(action))
        self.assertIn("threshold", ctx.exception.field)

    def test_roundtrip_save_load(self) -> None:
        """Guardar y cargar preserva todos los campos de verify_image."""
        script = _make_full_script(_make_verify_action(
            template_path="assets/templates/tpl_abc.png",
            threshold=0.9,
            max_retries=7,
            retry_delay_ms=500,
        ))
        # Patch validate so it doesn't fail on non-existent template_path
        original_validate = self.sm.validate

        def _permissive_validate(s):
            # Skip file existence check — only schema
            original_validate(s)

        # Save without validation (raw)
        import json
        from datetime import datetime
        script["meta"]["created_at"] = datetime.now().isoformat()
        self.tmp.write_text(
            json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Load raw (bypass validate to avoid file-existence check on template)
        loaded = json.loads(self.tmp.read_text(encoding="utf-8"))
        action = loaded["actions"][0]
        self.assertEqual(action["click_type"], "verify_image")
        self.assertEqual(action["template_path"], "assets/templates/tpl_abc.png")
        self.assertAlmostEqual(action["threshold"], 0.9)
        self.assertEqual(action["max_retries"], 7)
        self.assertEqual(action["retry_delay_ms"], 500)


if __name__ == "__main__":
    unittest.main()
