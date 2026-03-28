"""
core/orchestrator.py
====================
Central coordinator for mu-immortal-bot-macro-visual.

The Orchestrator owns no business logic.  Its sole responsibility is to
wire together ADBController, ScriptManager, BotEngine, and BotLogger,
delegate every operation to the appropriate specialist, and surface state
changes to the UI layer through the ``on_state_change`` callback.

Valid state strings emitted via on_state_change:
    "connecting"     – connect() has been called, ADB handshake in progress.
    "connected"      – ADB handshake succeeded.
    "running"        – Bot loop is active in the background thread.
    "stopped"        – Bot loop has finished or was stopped by the caller.
    "error"          – An unrecoverable error occurred; the bot is not running.
"""

import threading
from typing import Callable, Optional

from core.adb_controller import ADBController, ADBCommandError, ADBConnectionError
from core.bot_engine import BotEngine
from core.logger import BotLogger
from core.script_manager import ScriptManager, ScriptNotFoundError, ScriptValidationError
from core.visual_detector import VisualDetector


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ResolutionMismatchError(Exception):
    """Raised when the script's expected resolution differs from the device's.

    Attributes:
        script_res: Resolution dict from the script meta (``width`` / ``height``).
        device_res: Actual resolution tuple ``(width, height)`` from ADB.
    """

    def __init__(self, script_res: dict, device_res: tuple) -> None:
        self.script_res = script_res
        self.device_res = device_res
        sw, sh = script_res["width"], script_res["height"]
        dw, dh = device_res
        super().__init__(f"Script {sw}x{sh} \u2260 dispositivo {dw}x{dh}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Coordinates ADBController, ScriptManager, BotEngine, and BotLogger.

    All public methods are safe to call from the UI (main) thread.
    ``start_bot`` launches the engine in a daemon thread so the UI is
    never blocked.

    The optional ``on_state_change`` callable is invoked (from whatever
    thread triggered the transition) with a single string argument every
    time the application state changes.  Use a thread-safe bridge (e.g.
    a Qt signal) when wiring this to a GUI widget.

    Attributes:
        on_state_change: Optional[Callable[[str], None]]
            Set this after construction to receive state change notifications.
    """

    def __init__(self) -> None:
        """Instantiate all sub-systems and initialise internal state."""
        self._logger = BotLogger()
        self._script_manager = ScriptManager()
        self._adb = ADBController()
        self._detector = VisualDetector()
        self._engine = BotEngine(self._adb, self._logger, self._detector)

        self._script: Optional[dict] = None
        self._bot_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Public: wired by main.py after construction.
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_script_loaded: Optional[Callable[[dict], None]] = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _notify(self, state: str) -> None:
        """Invoke on_state_change if a handler has been registered.

        Args:
            state: State string to forward to the registered handler.
        """
        if self.on_state_change is not None:
            self.on_state_change(state)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self, host: str, port: int) -> None:
        """Connect to the ADB device at the given address.

        Sets ``ADBController.host`` and ``ADBController.port`` before
        attempting the connection.  Emits ``"connecting"`` immediately,
        then either ``"connected"`` or ``"error"``.

        Args:
            host: IP address of the emulator / device.
            port: ADB daemon TCP port.
        """
        self._adb.host = host
        self._adb.port = port
        # Mantener _script["emulator"] sincronizado si ya hay script en memoria
        if self._script is not None:
            self._script["emulator"] = {
                "host": host,
                "port": port,
            }
        self._notify("connecting")
        try:
            self._adb.connect()
            self._logger.info(f"Conectado a {host}:{port}")
            self._notify("connected")
        except ADBConnectionError as e:
            self._logger.error(f"Error de conexión: {e}")
            self._notify("error")

    def load_script(self, path: str) -> None:
        """Load and validate a script JSON file.

        On success, actions are forwarded to the engine via
        ``BotEngine.load_actions``.  Emits no explicit state change on
        success (callers may connect ``on_load`` and react there); emits
        ``"error"`` if loading or validation fails.

        Args:
            path: Filesystem path to the ``.json`` script file.
        """
        try:
            self._script = self._script_manager.load(path)
            self._logger.info(f"Script cargado: {path}")
            self._engine.load_actions(self._script["actions"])
            if self.on_script_loaded is not None:
                self.on_script_loaded(self._script)
        except (ScriptNotFoundError, ScriptValidationError) as e:
            self._logger.error(f"Error al cargar script: {e}")
            self._notify("error")

    def sync_ui_data(self, emulator: dict, cycle_delay: int) -> None:
        """Apply current UI field values to the in-memory script.

        Called by main.py just before saving so the JSON always reflects
        what the user sees on screen, regardless of whether they clicked
        Connect or Start first.

        Args:
            emulator:    Dict with host, port from the panel.
            cycle_delay: Cycle delay in milliseconds from the panel.
        """
        if self._script is None:
            return
        self._script["emulator"] = emulator
        self._script["cycle_delay"] = cycle_delay
        # Keep ADBController in sync too
        self._adb.host = emulator.get("host", self._adb.host)
        self._adb.port = emulator.get("port", self._adb.port)

    def save_script(self, path: str) -> bool:
        """Persist the currently loaded script to disk.

        Returns ``True`` on success, ``False`` otherwise.  Errors are logged
        but do not emit a state change (the save failing does not alter bot state).

        Args:
            path: Destination filesystem path for the ``.json`` file.
        """
        if self._script is None:
            self._logger.warn("save_script: no hay script en memoria, nada que guardar")
            return False
        try:
            self._script_manager.save(self._script, path)
            self._logger.info(f"Script guardado: {path}")
            return True
        except Exception as e:
            self._logger.error(f"Error al guardar script: {e}", exc=e)
            return False

    def sync_actions(self, actions: list) -> None:
        """Sync the action list from the UI canvas into the engine.

        Called every time the user adds, edits, deletes, toggles, or reorders
        ROIs in the canvas without loading a JSON script file.  Creates a
        minimal in-memory script if none is loaded yet, so start_bot() can
        proceed.

        Args:
            actions: Ordered list of action dicts from MainWindow.
        """
        self._engine.load_actions(actions)

        if self._script is None:
            # No JSON loaded — create a minimal in-memory script.
            # Resolution 0×0 signals validate_resolution() to skip the check.
            self._script = {
                "meta": {
                    "name": "Sin título",
                    "resolution": {"width": 0, "height": 0},
                    "created_at": "",
                    "version": "1.0",
                },
                "emulator": {
                    "host": self._adb.host,
                    "port": self._adb.port,
                },
                "actions": actions,
                "cycle_delay": 500,
            }
        else:
            self._script["actions"] = actions

    def validate_resolution(self) -> None:
        """Check that the device resolution matches the script's expected resolution.

        A no-op when no script is loaded.

        Raises:
            ResolutionMismatchError: If the two resolutions differ.

        Note:
            ADBCommandError during the ADB query is caught and logged as a
            warning; it does NOT raise so that callers in degraded
            connectivity can still proceed if they choose to.
        """
        if self._script is None:
            return
        try:
            device_res = self._adb.get_resolution()
            script_res = self._script["meta"]["resolution"]
            sw, sh = script_res["width"], script_res["height"]
            # 0×0 significa script creado desde UI sin referencia de resolución → omitir
            if sw == 0 and sh == 0:
                return
            dw, dh = device_res
            if sw != dw or sh != dh:
                raise ResolutionMismatchError(script_res, device_res)
        except ADBCommandError as e:
            self._logger.warn(f"No se pudo verificar resolución: {e}")

    def start_bot(self, cycles: int = 0, cycle_delay_ms: int = 500) -> None:
        """Launch the bot execution loop in a background daemon thread.

        Guards against double-start via an internal lock.  Validates
        resolution before starting; aborts with ``"error"`` if there is a
        mismatch.  Emits ``"running"`` once the thread is active.

        Args:
            cycles:         Number of full cycles to run (``0`` = infinite).
            cycle_delay_ms: Inter-cycle delay in milliseconds (currently
                            accepted but passed through for future use).
        """
        if self._script is None:
            self._logger.warn("No hay script cargado")
            return

        # Sincronizar cycle_delay de la UI al script antes de ejecutar/guardar
        self._script["cycle_delay"] = cycle_delay_ms

        try:
            self.validate_resolution()
        except ResolutionMismatchError as e:
            self._logger.error(str(e))
            self._notify("error")
            return

        with self._lock:
            if self._bot_thread is not None and self._bot_thread.is_alive():
                self._logger.warn("El bot ya está en ejecución")
                return

        # Configure engine callbacks.
        def _on_engine_error(exc: Exception) -> None:
            self._logger.error("Error en el bot", exc=exc)
            self._notify("error")

        def _on_cycle_complete(cycle: int) -> None:
            self._logger.info(f"Ciclo {cycle} completado")

        self._engine.on_error = _on_engine_error
        self._engine.on_cycle_complete = _on_cycle_complete

        # Open a new log session.
        self._logger.start_session(
            self._script["meta"]["name"],
            self._script["meta"]["resolution"],
            cycles,
        )

        # Launch the engine in a daemon thread.
        with self._lock:
            self._bot_thread = threading.Thread(
                target=self._engine.start,
                args=(cycles,),
                daemon=True,
                name="BotEngine",
            )
            self._bot_thread.start()

        self._notify("running")

    def stop_bot(self) -> None:
        """Signal the engine to stop and wait for the thread to finish.

        Safe to call even when the bot is not running (no-op in that case).
        Emits ``"stopped"`` after the thread has joined (or timed out).
        """
        self._engine.stop()

        with self._lock:
            thread = self._bot_thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

        self._logger.end_session(0, "stopped")
        self._notify("stopped")

        with self._lock:
            self._bot_thread = None

    def get_screenshot(self) -> Optional[object]:
        """Capture a screenshot from the connected device.

        Returns:
            A ``PIL.Image.Image`` object, or ``None`` if the capture fails.
        """
        try:
            return self._adb.screenshot()
        except Exception as e:
            self._logger.warn(f"No se pudo capturar pantalla: {e}")
            return None
