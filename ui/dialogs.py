"""
ui/dialogs.py
Reusable QDialog subclasses for the mu-immortal-bot-macro-visual project.
"""

import uuid
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

_ROI_SAVE_DIR = Path("assets/rois")
_TEMPLATE_SAVE_DIR = Path("assets/templates")


class ActionDialog(QDialog):
    """
    Dialog for creating or editing a macro action.

    Presents fields for action name, click type, delays, error handling,
    and the ROI pixel coordinates. If ``roi_preset`` is provided, the ROI
    fields are pre-filled with those values.

    If ``screenshot`` is provided, a "Guardar ROI como PNG" button is shown
    that crops and saves the selected region.
    """

    def __init__(
        self,
        parent=None,
        roi_preset: dict | None = None,
        screenshot: QPixmap | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar Acción")
        self._roi_preset = roi_preset
        self._screenshot = screenshot
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
        self._click_type.addItems(["single", "double", "long_press", "verify_image"])
        self._click_type.currentTextChanged.connect(self._on_click_type_changed)
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

        # --- Verify image section ---
        self._verify_group = QGroupBox("Verificación de imagen")
        verify_form = QFormLayout(self._verify_group)

        self._template_path_edit = QLineEdit()
        self._template_path_edit.setReadOnly(True)
        self._template_path_edit.setPlaceholderText("Guarda el ROI como PNG primero…")
        verify_form.addRow("Template PNG:", self._template_path_edit)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 1.0)
        self._threshold.setSingleStep(0.05)
        self._threshold.setValue(0.8)
        verify_form.addRow("Umbral (0-1):", self._threshold)

        self._max_retries = QSpinBox()
        self._max_retries.setRange(0, 20)
        self._max_retries.setValue(5)
        verify_form.addRow("Máx. reintentos:", self._max_retries)

        self._retry_delay_ms = QSpinBox()
        self._retry_delay_ms.setRange(0, 10000)
        self._retry_delay_ms.setSuffix(" ms")
        self._retry_delay_ms.setValue(1000)
        verify_form.addRow("Delay reintento:", self._retry_delay_ms)

        main_layout.addWidget(self._verify_group)

        # --- Save PNG button ---
        save_row = QHBoxLayout()
        self._btn_save_png = QPushButton("Guardar ROI como PNG…")
        self._btn_save_png.clicked.connect(self._save_roi_png)
        save_row.addStretch()
        save_row.addWidget(self._btn_save_png)
        main_layout.addLayout(save_row)

        # Configure initial visibility (also hides verify_group by default)
        self._on_click_type_changed(self._click_type.currentText())

        # --- Button box ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Save PNG
    # ------------------------------------------------------------------

    def _on_click_type_changed(self, text: str) -> None:
        """Show/hide the verify_image group and the save PNG button."""
        is_verify = (text == "verify_image")
        self._verify_group.setVisible(is_verify)
        self._btn_save_png.setVisible(
            self._screenshot is not None and (not is_verify or is_verify)
        )
        # For non-verify types, only show PNG button when screenshot available
        if not is_verify:
            self._btn_save_png.setVisible(self._screenshot is not None)

    def _save_roi_png(self) -> None:
        """Crop the current ROI from the screenshot and save as PNG."""
        if self._screenshot is None:
            return

        x = self._roi_x.value()
        y = self._roi_y.value()
        w = self._roi_w.value()
        h = self._roi_h.value()
        cropped = self._screenshot.copy(x, y, w, h)

        is_verify = self._click_type.currentText() == "verify_image"
        if is_verify:
            save_dir = _TEMPLATE_SAVE_DIR
            default_name = str(save_dir / f"tpl_{uuid.uuid4().hex[:8]}.png")
        else:
            save_dir = _ROI_SAVE_DIR
            default_name = str(save_dir / f"roi_{uuid.uuid4().hex[:8]}.png")

        save_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar ROI como PNG",
            default_name,
            "Imágenes PNG (*.png)",
        )
        if not path:
            return

        if not path.lower().endswith(".png"):
            path += ".png"

        if cropped.save(path, "PNG"):
            if is_verify:
                self._template_path_edit.setText(path)
            QMessageBox.information(self, "Guardado", f"ROI guardado en:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar la imagen.")

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
        if self._click_type.currentText() == "verify_image":
            if not self._template_path_edit.text().strip():
                QMessageBox.warning(
                    self,
                    "Template requerido",
                    "Guarda el ROI como PNG antes de confirmar.",
                )
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
        data = {
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
        if data["click_type"] == "verify_image":
            data["template_path"] = self._template_path_edit.text().strip()
            data["threshold"] = self._threshold.value()
            data["max_retries"] = self._max_retries.value()
            data["retry_delay_ms"] = self._retry_delay_ms.value()
        return data
