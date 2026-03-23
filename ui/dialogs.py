"""
ui/dialogs.py
Reusable QDialog subclasses for the mu-immortal-bot-macro-visual project.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QVBoxLayout,
    QLabel,
)
from PyQt6.QtCore import Qt


class ActionDialog(QDialog):
    """
    Dialog for creating or editing a macro action.

    Presents fields for action name, click type, delays, error handling,
    and the ROI pixel coordinates. If ``roi_preset`` is provided, the ROI
    fields are pre-filled with those values.
    """

    def __init__(self, parent=None, roi_preset: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar Acción")
        self._roi_preset = roi_preset
        self._setup_ui()
        self._prefill_roi(roi_preset)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build and assemble all widgets and layouts."""
        main_layout = QVBoxLayout(self)

        # --- Action section ---
        action_group = QGroupBox("Acción")
        action_form = QFormLayout(action_group)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Nombre de la acción")
        action_form.addRow("Nombre:", self._name)

        self._click_type = QComboBox()
        self._click_type.addItems(["single", "double", "long_press"])
        action_form.addRow("Click type:", self._click_type)

        self._delay_before = QSpinBox()
        self._delay_before.setRange(0, 9999)
        self._delay_before.setSuffix(" ms")
        action_form.addRow("Delay antes (ms):", self._delay_before)

        self._delay_after = QSpinBox()
        self._delay_after.setRange(0, 9999)
        self._delay_after.setSuffix(" ms")
        action_form.addRow("Delay después (ms):", self._delay_after)

        self._on_error = QComboBox()
        self._on_error.addItems(["stop", "skip"])
        action_form.addRow("On error:", self._on_error)

        main_layout.addWidget(action_group)

        # --- ROI section ---
        roi_group = QGroupBox("ROI (píxeles)")
        roi_form = QFormLayout(roi_group)

        self._roi_x = QSpinBox()
        self._roi_x.setRange(0, 9999)
        roi_form.addRow("X:", self._roi_x)

        self._roi_y = QSpinBox()
        self._roi_y.setRange(0, 9999)
        roi_form.addRow("Y:", self._roi_y)

        self._roi_w = QSpinBox()
        self._roi_w.setRange(1, 9999)
        roi_form.addRow("Ancho (w):", self._roi_w)

        self._roi_h = QSpinBox()
        self._roi_h.setRange(1, 9999)
        roi_form.addRow("Alto (h):", self._roi_h)

        main_layout.addWidget(roi_group)

        # --- Button box ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Pre-fill helpers
    # ------------------------------------------------------------------

    def _prefill_roi(self, roi_preset: dict | None) -> None:
        """Populate the ROI spinboxes from a preset dict if provided."""
        if roi_preset is None:
            return
        self._roi_x.setValue(roi_preset.get("x", 0))
        self._roi_y.setValue(roi_preset.get("y", 0))
        self._roi_w.setValue(roi_preset.get("w", 1))
        self._roi_h.setValue(roi_preset.get("h", 1))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_and_accept(self) -> None:
        """Validate inputs before closing with Accepted result."""
        if not self._name.text().strip():
            self._name.setFocus()
            self._name.setPlaceholderText("Ingresa un nombre")
            return
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_data(self) -> dict:
        """
        Return the dialog's current values as a dict compatible with the
        script JSON action format.

        Returns
        -------
        dict
            Keys: name, click_type, delay_before, delay_after, on_error, roi.
        """
        return {
            "name": self._name.text().strip(),
            "click_type": self._click_type.currentText(),
            "delay_before": self._delay_before.value(),
            "delay_after": self._delay_after.value(),
            "on_error": self._on_error.currentText(),
            "roi": {
                "x": self._roi_x.value(),
                "y": self._roi_y.value(),
                "w": self._roi_w.value(),
                "h": self._roi_h.value(),
            },
        }
