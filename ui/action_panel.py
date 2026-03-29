"""
ui/action_panel.py
Sidebar widget for configuring the emulator connection and managing macro
actions (list, reorder, enable/disable, run/stop).
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt6.QtGui import QPainter, QColor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_HOST: str = "127.0.0.1"
_DEFAULT_PORT: int = 5555
_DEFAULT_CYCLE_DELAY_MS: int = 500

# Custom data role that marks an item as the currently executing action.
_ACTIVE_ROLE = Qt.ItemDataRole.UserRole + 1

_DOT_RADIUS = 5
_DOT_MARGIN = 14   # distance from the right edge to the dot centre


# ---------------------------------------------------------------------------
# Item delegate — draws the green/grey activity dot
# ---------------------------------------------------------------------------

class _DotDelegate(QStyledItemDelegate):
    """Draws a small coloured circle at the centre-right of each list item.

    The dot is green when the item's ``_ACTIVE_ROLE`` data is ``True``,
    and grey otherwise.
    """

    _COLOR_ACTIVE = QColor("#27ae60")   # green
    _COLOR_IDLE   = QColor("#888888")   # grey

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        super().paint(painter, option, index)
        active: bool = bool(index.data(_ACTIVE_ROLE))
        color = self._COLOR_ACTIVE if active else self._COLOR_IDLE
        cx = option.rect.right() - _DOT_MARGIN
        cy = option.rect.center().y()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(
            cx - _DOT_RADIUS,
            cy - _DOT_RADIUS,
            _DOT_RADIUS * 2,
            _DOT_RADIUS * 2,
        )
        painter.restore()


class ActionPanel(QWidget):
    """
    Right-side panel that exposes controls for:
    - Emulator connection (host, port)
    - Action list management (enable/disable via checkboxes, drag-to-reorder)
    - Execution control (start / stop, cycle count, cycle delay)

    All user interactions are published as signals so the Orchestrator can
    react without the panel knowing anything about ``core/``.

    Signals
    -------
    connect_requested(str, int)
        Emitted when the user clicks "Conectar".
        Arguments: (host, port).
    action_toggled(str, bool)
        Emitted when the user changes the checked state of an action item.
        Arguments: (action_id, enabled).
    action_reordered(list)
        Emitted when the user reorders items via drag-and-drop.
        Argument: ordered list of action ids.
    start_requested(int, int)
        Emitted when the user clicks "Iniciar".
        Arguments: (cycles, cycle_delay_ms).
    stop_requested()
        Emitted when the user clicks "Detener".
    """

    connect_requested = pyqtSignal(str, int)
    refresh_requested = pyqtSignal()
    action_toggled = pyqtSignal(str, bool)
    action_reordered = pyqtSignal(list)
    start_requested = pyqtSignal(int, int)
    stop_requested = pyqtSignal()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Create all child widgets and assemble the layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        main_layout.addWidget(self._build_emulator_group())
        main_layout.addWidget(self._build_actions_group())
        main_layout.addWidget(self._build_execution_group())
        main_layout.addStretch(1)

        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------

    def _build_emulator_group(self) -> QGroupBox:
        """Build the "Emulador" connection group box."""
        group = QGroupBox("Emulador")
        form = QFormLayout(group)

        self._host = QLineEdit()
        self._host.setPlaceholderText(_DEFAULT_HOST)
        form.addRow("Host:", self._host)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(_DEFAULT_PORT)
        form.addRow("Puerto:", self._port)

        btn_row = QHBoxLayout()
        self._btn_connect = QPushButton("Conectar")
        self._btn_refresh = QPushButton("Refrescar captura  [F5]")
        self._btn_refresh.setEnabled(False)
        btn_row.addWidget(self._btn_connect)
        btn_row.addWidget(self._btn_refresh)
        form.addRow(btn_row)

        return group

    def _build_actions_group(self) -> QGroupBox:
        """Build the "Acciones" list group box with drag-and-drop support."""
        group = QGroupBox("Acciones")
        vbox = QVBoxLayout(group)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._list.setItemDelegate(_DotDelegate(self._list))
        vbox.addWidget(self._list)

        return group

    def _build_execution_group(self) -> QGroupBox:
        """Build the "Ejecución" run/stop group box."""
        group = QGroupBox("Ejecución")
        form = QFormLayout(group)

        self._cycles = QSpinBox()
        self._cycles.setRange(0, 99999)
        self._cycles.setValue(0)
        self._cycles.setSpecialValueText("∞")
        form.addRow("Ciclos (0=∞):", self._cycles)

        self._cycle_delay = QSpinBox()
        self._cycle_delay.setRange(0, 99999)
        self._cycle_delay.setValue(_DEFAULT_CYCLE_DELAY_MS)
        self._cycle_delay.setSuffix(" ms")
        form.addRow("Delay ciclo (ms):", self._cycle_delay)

        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶ Iniciar")
        self._btn_stop = QPushButton("■ Detener")
        self._btn_stop.setEnabled(False)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        form.addRow(btn_row)

        return group

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Connect all internal widget signals to slots or outgoing signals."""
        self._btn_connect.clicked.connect(self._emit_connect)
        self._btn_refresh.clicked.connect(self.refresh_requested.emit)
        self._btn_start.clicked.connect(self._emit_start)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        self._list.itemChanged.connect(self._on_item_changed)
        # Detect drag-and-drop reordering via the model's rowsMoved signal.
        self._list.model().rowsMoved.connect(self._on_rows_moved)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _emit_connect(self) -> None:
        """Gather connection fields and emit connect_requested."""
        host = self._host.text().strip() or _DEFAULT_HOST
        port = self._port.value()
        self.connect_requested.emit(host, port)

    def _emit_start(self) -> None:
        """Read run parameters and emit start_requested."""
        self.start_requested.emit(self._cycles.value(), self._cycle_delay.value())

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Re-emit action_toggled when a checkbox state changes."""
        roi_id: str = item.data(Qt.ItemDataRole.UserRole)
        enabled: bool = item.checkState() == Qt.CheckState.Checked
        self.action_toggled.emit(roi_id, enabled)

    def _on_rows_moved(self, *args) -> None:
        """Re-emit action_reordered with the new ordering of action ids."""
        ids = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]
        self.action_reordered.emit(ids)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_emulator(self) -> dict:
        """Return the current emulator field values as a dict."""
        return {
            "host": self._host.text().strip() or _DEFAULT_HOST,
            "port": self._port.value(),
        }

    def get_cycles(self) -> int:
        """Return the current number-of-cycles value (0 = infinite)."""
        return self._cycles.value()

    def get_cycle_delay(self) -> int:
        """Return the current cycle delay value in milliseconds."""
        return self._cycle_delay.value()

    def set_cycles(self, value: int) -> None:
        """Set the number-of-cycles spinbox from a loaded script."""
        self._cycles.setValue(value)

    def set_cycle_delay(self, value: int) -> None:
        """Set the cycle-delay spinbox from a loaded script."""
        self._cycle_delay.setValue(value)

    def set_emulator(self, emulator: dict) -> None:
        """Populate the emulator input fields from a loaded script.

        Parameters
        ----------
        emulator:
            Dict with keys ``host``, ``port``.
        """
        self._host.setText(emulator.get("host", ""))
        self._port.setValue(emulator.get("port", _DEFAULT_PORT))

    def set_actions(self, actions: list[dict]) -> None:
        """
        Populate the list widget from *actions*.

        Signals are blocked during population to avoid spurious
        ``action_toggled`` emissions.

        Parameters
        ----------
        actions:
            Ordered list of action dicts.  Each must contain at least
            ``id``, ``name``, and ``enabled``.
        """
        self._list.blockSignals(True)
        self._list.clear()

        for action in actions:
            item = QListWidgetItem(action.get("name", ""))
            item.setData(Qt.ItemDataRole.UserRole, action["id"])
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            check_state = (
                Qt.CheckState.Checked if action.get("enabled", True)
                else Qt.CheckState.Unchecked
            )
            item.setCheckState(check_state)
            self._list.addItem(item)

        self._list.blockSignals(False)

    def set_active_action(self, action_id: str | None) -> None:
        """Update the activity dot for all items.

        Sets the dot to green for the item whose id matches *action_id*,
        and to grey for all others.

        Parameters
        ----------
        action_id:
            Id of the currently executing action, or ``None`` to clear all.
        """
        for i in range(self._list.count()):
            item = self._list.item(i)
            is_active = (
                action_id is not None
                and item.data(Qt.ItemDataRole.UserRole) == action_id
            )
            item.setData(_ACTIVE_ROLE, is_active)
        self._list.viewport().update()

    def set_state(self, state: str) -> None:
        """
        Update button enabled states to reflect the application state.

        Parameters
        ----------
        state:
            One of ``'disconnected'``, ``'connected'``, ``'running'``,
            ``'error'``.
        """
        if state in ("connected", "stopped"):
            self._btn_connect.setEnabled(False)
            self._btn_refresh.setEnabled(True)
            self._btn_start.setEnabled(True)
            self._btn_stop.setEnabled(False)
        elif state == "running":
            self._btn_connect.setEnabled(False)
            self._btn_refresh.setEnabled(True)
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
        else:
            # 'disconnected' or 'error'
            self._btn_connect.setEnabled(True)
            self._btn_refresh.setEnabled(False)
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(False)
