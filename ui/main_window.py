"""
ui/main_window.py
Root application window for mu-immortal-bot-macro-visual.

This module is the sole integration point for all UI sub-widgets.
It owns no business logic — all external communication happens via
the public signals defined below, which the Orchestrator connects to
from outside the ui/ package.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QScrollArea,
    QToolBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QStatusBar,
)
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QPixmap, QKeySequence, QShortcut

from ui.roi_canvas import ROICanvas
from ui.action_panel import ActionPanel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WINDOW_TITLE: str = "MU Immortal Bot"
_MIN_WIDTH: int = 900
_MIN_HEIGHT: int = 600
_PANEL_WIDTH: int = 280

_STATE_LABELS: dict[str, tuple[str, str]] = {
    "disconnected": ("Desconectado", "#888888"),
    "connected":    ("Conectado",    "#27ae60"),
    "running":      ("Ejecutando",   "#2980b9"),
    "stopped":      ("Detenido",     "#27ae60"),
    "error":        ("Error",        "#e74c3c"),
}


class MainWindow(QMainWindow):
    """
    Primary window that hosts the ROICanvas (left) and ActionPanel (right).

    All external communication is exposed through the signals below.
    The Orchestrator must connect to these signals after constructing the
    window — MainWindow never calls into ``core/`` directly.

    Signals
    -------
    on_connect(str, int)
        Forwarded from ActionPanel.connect_requested.
        Arguments: (host, port).
    on_start(int, int)
        Forwarded from ActionPanel.start_requested.
        Arguments: (cycles, cycle_delay_ms).
    on_stop()
        Forwarded from ActionPanel.stop_requested.
    on_save(str)
        Emitted with the file path chosen in the Save dialog.
    on_load(str)
        Emitted with the file path chosen in the Open dialog.
    """

    on_connect = pyqtSignal(str, int)
    on_start = pyqtSignal(int, int)
    on_stop = pyqtSignal()
    on_save = pyqtSignal(str)
    on_load = pyqtSignal(str)
    on_refresh = pyqtSignal()
    on_actions_changed = pyqtSignal(list)   # emitida cuando la lista de acciones cambia

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rois: list[dict] = []
        self._current_path: str | None = None   # último archivo abierto / guardado
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Build the window layout: toolbar, splitter, status bar."""
        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)

        self._build_toolbar()
        self._build_central_widget()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        """Create the main toolbar with file actions and a status label."""
        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._act_new = QAction("Nuevo", self)

        self._act_open = QAction("Abrir", self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.setToolTip("Abrir script  (Ctrl+O)")

        self._act_save = QAction("Guardar", self)
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.setToolTip("Guardar script  (Ctrl+S)")

        self._act_quick_save = QAction("Guardar rápido", self)
        self._act_quick_save.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_quick_save.setToolTip("Guardar sin diálogo  (Ctrl+Shift+S)")

        toolbar.addAction(self._act_new)
        toolbar.addAction(self._act_open)
        toolbar.addAction(self._act_save)
        toolbar.addAction(self._act_quick_save)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Estado: "))

        self._status_label = QLabel("Desconectado")
        self._status_label.setStyleSheet("color: #888888; font-weight: bold;")
        toolbar.addWidget(self._status_label)

    def _build_central_widget(self) -> None:
        """Create the horizontal splitter with canvas (left) and panel (right)."""
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = ROICanvas()

        # Contenedor que centra el canvas dentro del scroll area.
        # setWidgetResizable(True) hace que el contenedor llene el viewport;
        # el canvas (tamaño fijo) queda centrado cuando el área es mayor,
        # y aparecen scrollbars cuando la imagen es más grande que el área.
        _container = QWidget()
        _layout = QVBoxLayout(_container)
        _layout.setContentsMargins(0, 0, 0, 0)
        _layout.addWidget(self._canvas, 0, Qt.AlignmentFlag.AlignCenter)

        self._scroll = QScrollArea()
        self._scroll.setWidget(_container)
        self._scroll.setWidgetResizable(True)

        self._panel = ActionPanel()
        self._panel.setFixedWidth(_PANEL_WIDTH)

        splitter.addWidget(self._scroll)
        splitter.addWidget(self._panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def _build_status_bar(self) -> None:
        """Attach a QStatusBar for brief transient messages."""
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal signals between sub-widgets and outward signals."""
        # Panel → outward signals
        self._panel.connect_requested.connect(self.on_connect)
        self._panel.refresh_requested.connect(self.on_refresh)
        self._panel.start_requested.connect(self.on_start)
        self._panel.stop_requested.connect(self.on_stop)

        # Hotkey global de emergencia: Escape detiene el bot
        _emergency_stop = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        _emergency_stop.activated.connect(self.on_stop)

        # Toolbar actions
        self._act_new.triggered.connect(self._action_new)
        self._act_open.triggered.connect(self._action_open)
        self._act_save.triggered.connect(self._action_save)
        self._act_quick_save.triggered.connect(self._action_quick_save)

        # Canvas ROI signals → internal state update + panel sync
        self._canvas.roi_created.connect(self._on_roi_created)
        self._canvas.roi_edited.connect(self._on_roi_edited)
        self._canvas.roi_deleted.connect(self._on_roi_deleted)

        # Panel action list changes → update internal state
        self._panel.action_toggled.connect(self._on_action_toggled)
        self._panel.action_reordered.connect(self._on_action_reordered)

    # ------------------------------------------------------------------
    # Public API (called by the Orchestrator)
    # ------------------------------------------------------------------

    def set_current_path(self, path: str) -> None:
        """Inform the window of the active script path (called by the Orchestrator)."""
        self._current_path = path

    def get_emulator_config(self) -> dict:
        """Return the current emulator field values from the panel."""
        return self._panel.get_emulator()

    def get_cycle_delay(self) -> int:
        """Return the current cycle delay value from the panel."""
        return self._panel.get_cycle_delay()

    def set_screenshot(self, pixmap: QPixmap) -> None:
        """
        Push a new screenshot onto the canvas.

        Parameters
        ----------
        pixmap:
            The captured frame to display as the canvas background.
        """
        self._canvas.set_screenshot(pixmap)

    def set_rois(self, rois: list[dict]) -> None:
        """
        Synchronise both the canvas overlay and the action panel list.

        Parameters
        ----------
        rois:
            Ordered list of action dicts to display and manage.
        """
        self._rois = list(rois)
        self._canvas.set_rois(self._rois)
        self._panel.set_actions(self._rois)
        self.on_actions_changed.emit(self._rois)

    def set_state(self, state: str) -> None:
        """
        Update the visual state indicator and action panel button states.

        Parameters
        ----------
        state:
            One of ``'disconnected'``, ``'connected'``, ``'running'``,
            ``'error'``.
        """
        text, color = _STATE_LABELS.get(state, ("Desconocido", "#888888"))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._panel.set_state(state)

    # ------------------------------------------------------------------
    # Toolbar action slots
    # ------------------------------------------------------------------

    def _action_new(self) -> None:
        """Clear the current script after user confirmation."""
        answer = QMessageBox.question(
            self,
            "Nuevo script",
            "¿Descartar el script actual y comenzar uno nuevo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.set_rois([])

    def _action_open(self) -> None:
        """Open a file dialog and emit on_load with the chosen path."""
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir script", scripts_dir, "JSON (*.json)"
        )
        if path:
            self._current_path = path
            self.on_load.emit(path)

    def _action_save(self) -> None:
        """Open a save dialog pre-filled with a sensible default name."""
        default = self._current_path or self._default_save_path()
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar script", default, "JSON (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            self._current_path = path
            self.on_save.emit(path)

    def _action_quick_save(self) -> None:
        """Save directly to the current path (or a generated one) without a dialog."""
        path = self._current_path or self._default_save_path()
        if not path.lower().endswith(".json"):
            path += ".json"
        self.on_save.emit(path)

    def _default_save_path(self) -> str:
        """Return an absolute timestamped path inside the project's scripts/ folder."""
        name = datetime.now().strftime("script_%Y%m%d_%H%M%S")
        scripts_dir = Path(__file__).parent.parent / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        return str(scripts_dir / f"{name}.json")

    # ------------------------------------------------------------------
    # Canvas signal handlers
    # ------------------------------------------------------------------

    def _on_roi_created(self, data: dict) -> None:
        """
        Append the new ROI action to the internal list and refresh both
        the canvas and the panel.
        """
        self._rois.append(data)
        self.set_rois(self._rois)

    def _on_roi_edited(self, roi_id: str, data: dict) -> None:
        """
        Update the fields of an existing ROI action in-place, preserving
        its ``id`` and ``enabled`` state unless the caller overrides them.
        """
        for i, roi in enumerate(self._rois):
            if roi["id"] == roi_id:
                # Keep the id; caller may not include it.
                data["id"] = roi_id
                # Preserve enabled state if the dialog didn't set it.
                data.setdefault("enabled", roi.get("enabled", True))
                self._rois[i] = data
                break
        self.set_rois(self._rois)

    def _on_roi_deleted(self, roi_id: str) -> None:
        """Remove the ROI with the given id and refresh the UI."""
        self._rois = [r for r in self._rois if r["id"] != roi_id]
        self.set_rois(self._rois)

    def _on_action_toggled(self, roi_id: str, enabled: bool) -> None:
        """Update the enabled state of an action from the panel checkbox."""
        for roi in self._rois:
            if roi["id"] == roi_id:
                roi["enabled"] = enabled
                break
        self.on_actions_changed.emit(self._rois)

    def _on_action_reordered(self, ordered_ids: list) -> None:
        """Reorder internal ROI list to match the panel drag-and-drop order."""
        id_to_roi = {r["id"]: r for r in self._rois}
        self._rois = [id_to_roi[i] for i in ordered_ids if i in id_to_roi]
        self._canvas.set_rois(self._rois)
        self.on_actions_changed.emit(self._rois)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """
        Intercept the close event to allow graceful shutdown.

        The Orchestrator should connect to ``on_stop`` to halt any running
        macro before the window disappears.  Here we simply emit on_stop
        (a no-op if nothing is running) and then accept the event.
        """
        self.on_stop.emit()
        event.accept()
