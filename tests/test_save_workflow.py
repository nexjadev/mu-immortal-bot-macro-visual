"""
tests/test_save_workflow.py
===========================
Functional tests for the script save workflow.

These tests exercise the full save pipeline WITHOUT mocking ScriptManager,
to catch silent failures (no file written, wrong path, etc.) that pure unit
tests with mocks would miss.

Escenarios cubiertos:
  1. save_script devuelve False cuando _script es None.
  2. sync_actions inicializa _script cuando era None.
  3. Flujo completo: sync_actions → sync_ui_data → save_script crea el archivo.
  4. El archivo contiene JSON válido con los datos correctos.
  5. save_script devuelve True en éxito y False si ScriptManager lanza excepción.
  6. sync_ui_data actualiza host/port en el script en memoria.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Mockear PIL si no está instalado para no bloquear la importación.
if "PIL" not in sys.modules:
    _pil = MagicMock()
    sys.modules["PIL"] = _pil
    sys.modules["PIL.Image"] = _pil.Image

from core.orchestrator import Orchestrator


def _make_roi(name: str = "TestClick") -> dict:
    """ROI action mínimo válido."""
    return {
        "id": "abc123",
        "name": name,
        "enabled": True,
        "roi": {"x": 10, "y": 20, "w": 100, "h": 50},
        "click_type": "single",
        "delay_before": 0,
        "delay_after": 0,
        "on_error": "stop",
    }


class TestSaveWorkflow(unittest.TestCase):
    """Pruebas funcionales del flujo completo de guardado de scripts."""

    def setUp(self) -> None:
        self.orc = Orchestrator()
        # Mockear solo ADB y logger para no necesitar dispositivo ni archivos de log.
        self.orc._adb = MagicMock()
        self.orc._adb.host = "127.0.0.1"   # valores reales: json.dumps los serializa
        self.orc._adb.port = 5555
        self.orc._logger = MagicMock()
        # ScriptManager real — queremos probar el I/O real.

        self.tmp_dir = tempfile.mkdtemp()
        self.save_path = str(Path(self.tmp_dir) / "test_script.json")

    # ------------------------------------------------------------------
    # 1. save_script retorna False cuando _script es None
    # ------------------------------------------------------------------

    def test_save_returns_false_when_script_is_none(self) -> None:
        """save_script debe retornar False (sin escribir nada) si _script es None."""
        result = self.orc.save_script(self.save_path)

        self.assertFalse(result, "save_script debería retornar False cuando _script es None")
        self.assertFalse(Path(self.save_path).exists(), "No debe crearse ningún archivo")

    # ------------------------------------------------------------------
    # 2. sync_actions inicializa _script cuando era None
    # ------------------------------------------------------------------

    def test_sync_actions_initializes_script_when_none(self) -> None:
        """sync_actions debe crear un script en memoria si _script era None."""
        self.assertIsNone(self.orc._script)

        self.orc.sync_actions([_make_roi()])

        self.assertIsNotNone(self.orc._script)
        self.assertIn("meta", self.orc._script)
        self.assertIn("emulator", self.orc._script)
        self.assertIn("actions", self.orc._script)
        self.assertEqual(len(self.orc._script["actions"]), 1)

    # ------------------------------------------------------------------
    # 3. Flujo completo: el archivo se crea en disco
    # ------------------------------------------------------------------

    def test_full_save_creates_file(self) -> None:
        """El flujo sync_actions → sync_ui_data → save_script debe crear el archivo."""
        rois = [_make_roi("Boton1"), _make_roi("Boton2")]
        rois[1]["id"] = "def456"

        self.orc.sync_actions(rois)
        self.orc.sync_ui_data(
            emulator={"host": "127.0.0.1", "port": 5555},
            cycle_delay=300,
        )
        result = self.orc.save_script(self.save_path)

        self.assertTrue(result, "save_script debe retornar True al guardar con éxito")
        self.assertTrue(Path(self.save_path).exists(), "El archivo debe existir en disco")

    # ------------------------------------------------------------------
    # 4. El contenido del archivo es JSON válido con los datos correctos
    # ------------------------------------------------------------------

    def test_saved_file_contains_correct_data(self) -> None:
        """El archivo guardado debe contener host, port y las acciones correctas."""
        roi = _make_roi("ClickPrincipal")
        self.orc.sync_actions([roi])
        self.orc.sync_ui_data(
            emulator={"host": "10.0.0.2", "port": 5556},
            cycle_delay=750,
        )
        self.orc.save_script(self.save_path)

        content = json.loads(Path(self.save_path).read_text(encoding="utf-8"))

        self.assertEqual(content["emulator"]["host"], "10.0.0.2")
        self.assertEqual(content["emulator"]["port"], 5556)
        self.assertEqual(content["cycle_delay"], 750)
        self.assertEqual(len(content["actions"]), 1)
        self.assertEqual(content["actions"][0]["name"], "ClickPrincipal")

    # ------------------------------------------------------------------
    # 5. save_script retorna False si ScriptManager lanza excepción
    # ------------------------------------------------------------------

    def test_save_returns_false_on_exception(self) -> None:
        """save_script debe retornar False y loggear si hay error de escritura."""
        self.orc.sync_actions([_make_roi()])

        # Reemplazar ScriptManager por mock que lanza IOError.
        self.orc._script_manager = MagicMock()
        self.orc._script_manager.save.side_effect = IOError("permiso denegado")

        result = self.orc.save_script(self.save_path)

        self.assertFalse(result)
        self.assertTrue(self.orc._logger.error.called)

    # ------------------------------------------------------------------
    # 6. sync_ui_data sincroniza host/port en ADBController
    # ------------------------------------------------------------------

    def test_sync_ui_data_updates_adb_host_port(self) -> None:
        """sync_ui_data debe actualizar self._adb.host y self._adb.port."""
        self.orc.sync_actions([_make_roi()])
        self.orc.sync_ui_data(
            emulator={"host": "192.168.1.10", "port": 7777},
            cycle_delay=0,
        )

        self.assertEqual(self.orc._adb.host, "192.168.1.10")
        self.assertEqual(self.orc._adb.port, 7777)

    # ------------------------------------------------------------------
    # 7. save_script sobreescribe el archivo si ya existe
    # ------------------------------------------------------------------

    def test_save_overwrites_existing_file(self) -> None:
        """Guardar dos veces debe sobreescribir el archivo, no duplicarlo."""
        self.orc.sync_actions([_make_roi("V1")])
        self.orc.save_script(self.save_path)

        # Segunda pasada con datos diferentes.
        self.orc._script["actions"][0]["name"] = "V2"
        self.orc.save_script(self.save_path)

        content = json.loads(Path(self.save_path).read_text(encoding="utf-8"))
        self.assertEqual(content["actions"][0]["name"], "V2")

    # ------------------------------------------------------------------
    # 8. cycles se guarda y se preserva en el JSON
    # ------------------------------------------------------------------

    def test_cycles_saved_to_json(self) -> None:
        """sync_ui_data con cycles=5 debe persistir cycles=5 en el JSON guardado."""
        self.orc.sync_actions([_make_roi()])
        self.orc.sync_ui_data(
            emulator={"host": "127.0.0.1", "port": 5555},
            cycle_delay=500,
            cycles=5,
        )
        self.orc.save_script(self.save_path)

        content = json.loads(Path(self.save_path).read_text(encoding="utf-8"))
        self.assertEqual(content["cycles"], 5)

    def test_cycles_default_zero_when_not_passed(self) -> None:
        """sync_ui_data sin cycles debe guardar cycles=0 (por defecto)."""
        self.orc.sync_actions([_make_roi()])
        self.orc.sync_ui_data(
            emulator={"host": "127.0.0.1", "port": 5555},
            cycle_delay=200,
        )
        self.orc.save_script(self.save_path)

        content = json.loads(Path(self.save_path).read_text(encoding="utf-8"))
        self.assertEqual(content["cycles"], 0)


if __name__ == "__main__":
    unittest.main()
