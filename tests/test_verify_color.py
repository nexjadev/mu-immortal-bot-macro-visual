"""
tests/test_verify_color.py
==========================
Tests para la acción verify_color:
  - VisualDetector.find_color()  (requiere numpy; skip si no está)
  - BotEngine con verify_color   (detector mockeado)
  - ScriptManager validación     (real)
"""

import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mocks de dependencias opcionales ANTES de cualquier import de core/
# ---------------------------------------------------------------------------
# PIL se mockea siempre para que los imports de core/ no fallen.
if "PIL" not in sys.modules:
    pil_mock = MagicMock()
    pil_mock.Image = MagicMock()
    sys.modules["PIL"] = pil_mock
    sys.modules["PIL.Image"] = pil_mock.Image

# Detectar si numpy está disponible para los tests de detector real.
try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from core.bot_engine import BotEngine
from core.script_manager import ScriptManager, ScriptValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verify_color_action(
    action_id: str = "vc01",
    name: str = "CheckColor",
    target_color: list | None = None,
    color_tolerance: int = 30,
    min_ratio: float = 0.05,
    max_retries: int = 0,
    retry_delay_ms: int = 0,
    on_found: str = "next",
    on_found_target_id: str | None = None,
    on_not_found: str = "stop",
    on_not_found_target_id: str | None = None,
) -> dict:
    action = {
        "id": action_id,
        "name": name,
        "enabled": True,
        "click_type": "verify_color",
        "roi": {"x": 0, "y": 0, "w": 10, "h": 10},
        "target_color": target_color if target_color is not None else [255, 0, 0],
        "color_tolerance": color_tolerance,
        "min_ratio": min_ratio,
        "max_retries": max_retries,
        "retry_delay_ms": retry_delay_ms,
        "on_found": on_found,
        "on_found_target_id": on_found_target_id,
        "on_not_found": on_not_found,
        "on_not_found_target_id": on_not_found_target_id,
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "stop",
    }
    return action


def _make_click_action(action_id: str = "cl01", name: str = "Click") -> dict:
    return {
        "id": action_id,
        "name": name,
        "enabled": True,
        "click_type": "single",
        "roi": {"x": 0, "y": 0, "w": 1, "h": 1},
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "stop",
    }


def _make_full_script(actions: list) -> dict:
    return {
        "meta": {
            "name": "Test Script",
            "resolution": {"width": 0, "height": 0},
            "created_at": "",
            "version": "1.0",
        },
        "emulator": {"host": "127.0.0.1", "port": 5555},
        "actions": actions,
        "cycle_delay": 0,
        "cycles": 0,
    }


# ---------------------------------------------------------------------------
# 1. VisualDetector.find_color()
# ---------------------------------------------------------------------------

@unittest.skipUnless(_NUMPY_AVAILABLE, "numpy no instalado")
class TestVisualDetectorFindColor(unittest.TestCase):
    """Tests de integración real contra find_color() (requiere numpy)."""

    def setUp(self):
        # Importamos aquí para que el mock de PIL no interfiera con el import real.
        from PIL import Image as PilImage
        import numpy as np
        self._Image = PilImage
        self._np = np

        # Desvinculamos el mock global para estos tests
        from core.visual_detector import VisualDetector
        self.detector = VisualDetector()

    def _solid_image(self, color: tuple, size: tuple = (100, 100)):
        """Crea una imagen PIL de color sólido."""
        img = self._Image.new("RGB", size, color)
        return img

    def test_color_found_exact(self):
        """Color exacto con tolerance=0 en imagen sólida → True."""
        img = self._solid_image((200, 100, 50))
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        result = self.detector.find_color(img, roi, [200, 100, 50], tolerance=0, min_ratio=0.01)
        self.assertTrue(result)

    def test_color_not_found(self):
        """Color completamente diferente → False."""
        img = self._solid_image((200, 100, 50))
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        result = self.detector.find_color(img, roi, [0, 255, 0], tolerance=0, min_ratio=0.01)
        self.assertFalse(result)

    def test_color_within_tolerance(self):
        """Color off by 20 en cada canal, tolerance=25 → True."""
        img = self._solid_image((200, 100, 50))
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        # target: (180, 80, 30) — difiere en 20 por canal
        result = self.detector.find_color(img, roi, [180, 80, 30], tolerance=25, min_ratio=0.01)
        self.assertTrue(result)

    def test_color_outside_tolerance(self):
        """Color off by 20, tolerance=10 → False."""
        img = self._solid_image((200, 100, 50))
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        result = self.detector.find_color(img, roi, [180, 80, 30], tolerance=10, min_ratio=0.01)
        self.assertFalse(result)

    def test_min_ratio_not_met(self):
        """Solo el 1% de píxeles coincide pero min_ratio=0.05 → False."""
        import numpy as np
        # Imagen 100x100 = 10000px; ponemos un bloque 10x10=100px (1%) en rojo.
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        arr[0:10, 0:10] = [255, 0, 0]
        img = self._Image.fromarray(arr, "RGB")
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        result = self.detector.find_color(img, roi, [255, 0, 0], tolerance=5, min_ratio=0.05)
        self.assertFalse(result)

    def test_min_ratio_met(self):
        """10% de píxeles coincide con min_ratio=0.05 → True."""
        import numpy as np
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        arr[0:10, :] = [255, 0, 0]   # 10 filas × 100 cols = 1000px = 10%
        img = self._Image.fromarray(arr, "RGB")
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}
        result = self.detector.find_color(img, roi, [255, 0, 0], tolerance=5, min_ratio=0.05)
        self.assertTrue(result)

    def test_invalid_tolerance_raises(self):
        """tolerance=300 → ValueError."""
        img = self._solid_image((0, 0, 0))
        roi = {"x": 0, "y": 0, "w": 10, "h": 10}
        with self.assertRaises(ValueError):
            self.detector.find_color(img, roi, [0, 0, 0], tolerance=300)

    def test_invalid_min_ratio_raises(self):
        """min_ratio=1.5 → ValueError."""
        img = self._solid_image((0, 0, 0))
        roi = {"x": 0, "y": 0, "w": 10, "h": 10}
        with self.assertRaises(ValueError):
            self.detector.find_color(img, roi, [0, 0, 0], tolerance=10, min_ratio=1.5)

    def test_invalid_target_color_raises(self):
        """target_color con valor fuera de rango → ValueError."""
        img = self._solid_image((0, 0, 0))
        roi = {"x": 0, "y": 0, "w": 10, "h": 10}
        with self.assertRaises(ValueError):
            self.detector.find_color(img, roi, [300, 0, 0], tolerance=10)

    def test_roi_cropping(self):
        """El color existe fuera del ROI pero no dentro → False."""
        import numpy as np
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        arr[80:, :] = [255, 0, 0]    # rojo solo en filas 80-99
        img = self._Image.fromarray(arr, "RGB")
        roi = {"x": 0, "y": 0, "w": 100, "h": 50}   # solo primeras 50 filas
        result = self.detector.find_color(img, roi, [255, 0, 0], tolerance=5, min_ratio=0.01)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 2. BotEngine con verify_color (detector mockeado)
# ---------------------------------------------------------------------------

class TestBotEngineVerifyColor(unittest.TestCase):
    """Tests del motor de ejecución con verify_color; detector totalmente mockeado."""

    def setUp(self):
        self.adb = MagicMock()
        self.adb.tap = MagicMock()
        self.logger = MagicMock()
        self.detector = MagicMock()
        self.detector.get_frame.return_value = MagicMock()
        self.errors = []

        self.engine = BotEngine(
            adb=self.adb,
            logger=self.logger,
            detector=self.detector,
        )
        self.engine.on_error = lambda e: self.errors.append(e)

    def _run_once(self):
        self.engine.start(cycles=1)

    def test_found_next_advances_to_next_action(self):
        """find_color=True, on_found=next → la acción siguiente se ejecuta."""
        self.detector.find_color.return_value = True
        vc = _make_verify_color_action(on_found="next", on_not_found="stop")
        click = _make_click_action()
        self.engine.load_actions([vc, click])
        self._run_once()
        self.adb.tap.assert_called_once()

    def test_not_found_stop_halts_bot(self):
        """find_color=False, on_not_found=stop → bot se detiene, no ejecuta click."""
        self.detector.find_color.return_value = False
        vc = _make_verify_color_action(on_found="next", on_not_found="stop")
        click = _make_click_action()
        self.engine.load_actions([vc, click])
        self._run_once()
        self.adb.tap.assert_not_called()

    def test_found_stop_halts_bot(self):
        """find_color=True, on_found=stop → bot se detiene."""
        self.detector.find_color.return_value = True
        vc = _make_verify_color_action(on_found="stop", on_not_found="next")
        click = _make_click_action()
        self.engine.load_actions([vc, click])
        self._run_once()
        self.adb.tap.assert_not_called()

    def test_not_found_next_continues(self):
        """find_color=False, on_not_found=next → la acción siguiente se ejecuta."""
        self.detector.find_color.return_value = False
        vc = _make_verify_color_action(on_found="stop", on_not_found="next")
        click = _make_click_action()
        self.engine.load_actions([vc, click])
        self._run_once()
        self.adb.tap.assert_called_once()

    def test_found_goto_jumps_to_target(self):
        """find_color=True, on_found=goto → salta a target, omite intermedias."""
        self.detector.find_color.return_value = True
        target = _make_click_action(action_id="target01", name="Target")
        skipped = _make_click_action(action_id="skip01", name="Skipped")
        vc = _make_verify_color_action(
            on_found="goto", on_found_target_id="target01",
            on_not_found="stop",
        )
        # Orden: vc → skipped → target
        self.engine.load_actions([vc, skipped, target])
        call_order = []
        orig_tap = self.adb.tap.side_effect
        self.adb.tap.side_effect = lambda x, y: call_order.append((x, y))
        self._run_once()
        # Solo "target" debe ejecutarse (goto salta "skipped")
        self.assertEqual(self.adb.tap.call_count, 1)

    def test_verify_color_does_not_tap(self):
        """verify_color nunca llama a adb.tap independientemente del resultado."""
        for result in (True, False):
            self.adb.tap.reset_mock()
            self.detector.find_color.return_value = result
            vc = _make_verify_color_action(on_found="next", on_not_found="next")
            self.engine.load_actions([vc])
            self._run_once()
            self.adb.tap.assert_not_called()

    def test_retries_until_found(self):
        """find_color=False, False, True → 3 llamadas a get_frame."""
        self.detector.find_color.side_effect = [False, False, True]
        vc = _make_verify_color_action(max_retries=2, retry_delay_ms=0, on_found="next", on_not_found="stop")
        self.engine.load_actions([vc])
        self._run_once()
        self.assertEqual(self.detector.get_frame.call_count, 3)

    def test_retries_exhausted_takes_not_found_branch(self):
        """Todos los reintentos agotan → toma on_not_found."""
        self.detector.find_color.return_value = False
        click = _make_click_action()
        vc = _make_verify_color_action(
            max_retries=2, retry_delay_ms=0,
            on_found="next", on_not_found="stop",
        )
        self.engine.load_actions([vc, click])
        self._run_once()
        # on_not_found=stop → click no ejecutado
        self.adb.tap.assert_not_called()
        # 3 intentos (max_retries=2 → 2+1)
        self.assertEqual(self.detector.get_frame.call_count, 3)

    def test_stop_during_retries_exits_early(self):
        """engine.stop() desde dentro del reintento detiene el loop."""
        def _find_color_and_stop(*args, **kwargs):
            self.engine.stop()
            return False

        self.detector.find_color.side_effect = _find_color_and_stop
        vc = _make_verify_color_action(max_retries=5, retry_delay_ms=0, on_not_found="next")
        self.engine.load_actions([vc])

        t = threading.Thread(target=self._run_once)
        t.start()
        t.join(timeout=3)
        self.assertFalse(t.is_alive())
        # Solo 1 intento antes de que stop_event interrumpa
        self.assertEqual(self.detector.find_color.call_count, 1)


# ---------------------------------------------------------------------------
# 3. ScriptManager — validación de verify_color
# ---------------------------------------------------------------------------

class TestScriptManagerVerifyColor(unittest.TestCase):
    """Tests de validación y round-trip de verify_color en ScriptManager."""

    def setUp(self):
        self.sm = ScriptManager()

    def _validate(self, actions):
        script = _make_full_script(actions)
        self.sm.validate(script)

    def test_valid_verify_color_passes(self):
        """Acción verify_color completa y válida no lanza excepción."""
        self._validate([_make_verify_color_action()])

    def test_missing_target_color_raises(self):
        action = _make_verify_color_action()
        del action["target_color"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("target_color", ctx.exception.field)

    def test_target_color_wrong_type_raises(self):
        action = _make_verify_color_action()
        action["target_color"] = "rojo"
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("target_color", ctx.exception.field)

    def test_target_color_out_of_range_raises(self):
        action = _make_verify_color_action()
        action["target_color"] = [300, 0, 0]
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("target_color", ctx.exception.field)

    def test_target_color_wrong_length_raises(self):
        action = _make_verify_color_action()
        action["target_color"] = [255, 0]
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("target_color", ctx.exception.field)

    def test_invalid_color_tolerance_raises(self):
        action = _make_verify_color_action()
        action["color_tolerance"] = 300
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("color_tolerance", ctx.exception.field)

    def test_missing_color_tolerance_raises(self):
        action = _make_verify_color_action()
        del action["color_tolerance"]
        with self.assertRaises(ScriptValidationError):
            self._validate([action])

    def test_invalid_min_ratio_raises(self):
        action = _make_verify_color_action()
        action["min_ratio"] = 1.5
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("min_ratio", ctx.exception.field)

    def test_missing_on_found_raises(self):
        action = _make_verify_color_action()
        del action["on_found"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("on_found", ctx.exception.field)

    def test_invalid_on_found_value_raises(self):
        action = _make_verify_color_action()
        action["on_found"] = "continue"
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("on_found", ctx.exception.field)

    def test_missing_on_not_found_raises(self):
        action = _make_verify_color_action()
        del action["on_not_found"]
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("on_not_found", ctx.exception.field)

    def test_goto_without_target_id_raises(self):
        action = _make_verify_color_action(on_found="goto")
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("on_found_target_id", ctx.exception.field)

    def test_not_found_goto_without_target_id_raises(self):
        action = _make_verify_color_action(on_not_found="goto")
        with self.assertRaises(ScriptValidationError) as ctx:
            self._validate([action])
        self.assertIn("on_not_found_target_id", ctx.exception.field)

    def test_roundtrip_save_load_preserves_fields(self):
        """Guardar y cargar un script con verify_color preserva todos los campos."""
        import json
        import tempfile
        import os

        action = _make_verify_color_action(
            target_color=[128, 64, 32],
            color_tolerance=20,
            min_ratio=0.10,
            max_retries=3,
            retry_delay_ms=500,
            on_found="next",
            on_not_found="stop",
        )
        script = _make_full_script([action])

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            path = f.name

        try:
            self.sm.save(script, path)
            loaded = self.sm.load(path)
            a = loaded["actions"][0]
            self.assertEqual(a["target_color"], [128, 64, 32])
            self.assertEqual(a["color_tolerance"], 20)
            self.assertAlmostEqual(a["min_ratio"], 0.10, places=5)
            self.assertEqual(a["max_retries"], 3)
            self.assertEqual(a["retry_delay_ms"], 500)
            self.assertEqual(a["on_found"], "next")
            self.assertEqual(a["on_not_found"], "stop")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
