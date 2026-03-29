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
    QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor, QColor

_ROI_SAVE_DIR = Path("assets/rois")
_TEMPLATE_SAVE_DIR = Path("assets/templates")

# Mapping between QComboBox display text and the JSON field value.
_BRANCH_LABELS = ["Siguiente acción", "Ir a acción...", "Detener"]
_BRANCH_VALUES = ["next", "goto", "stop"]


# ---------------------------------------------------------------------------
# Color picker overlay dialog
# ---------------------------------------------------------------------------

class ColorPickerDialog(QDialog):
    """Muestra el screenshot y permite al usuario hacer clic en un píxel
    para capturar su color RGB.

    El diálogo escala la imagen para que quepa en pantalla manteniendo
    la relación de aspecto.  El color se lee sobre la imagen original
    (sin escalar) para mayor precisión.
    """

    def __init__(self, screenshot: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Seleccionar color — haz clic en el píxel deseado")
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self._screenshot = screenshot
        self._selected_color: QColor | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        hint = QLabel("Haz clic sobre el color que deseas capturar.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Escalar imagen para que quepa en la pantalla disponible.
        scaled = self._screenshot.scaled(
            1200, 700,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._scale_x = self._screenshot.width() / max(scaled.width(), 1)
        self._scale_y = self._screenshot.height() / max(scaled.height(), 1)

        self._img_label = QLabel()
        self._img_label.setPixmap(scaled)
        self._img_label.setFixedSize(scaled.size())
        self._img_label.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        scroll = QScrollArea()
        scroll.setWidget(self._img_label)
        scroll.setWidgetResizable(False)
        layout.addWidget(scroll)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignRight)

    def mousePressEvent(self, event) -> None:
        """Captura el color del píxel si el clic fue sobre la imagen."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # Mapear posición global al label de imagen.
        pos_in_label = self._img_label.mapFromGlobal(
            self.mapToGlobal(event.pos())
        )
        lw, lh = self._img_label.width(), self._img_label.height()
        if not (0 <= pos_in_label.x() < lw and 0 <= pos_in_label.y() < lh):
            return
        # Convertir coordenadas escala-label → coordenadas imagen original.
        orig_x = int(pos_in_label.x() * self._scale_x)
        orig_y = int(pos_in_label.y() * self._scale_y)
        orig_x = max(0, min(orig_x, self._screenshot.width() - 1))
        orig_y = max(0, min(orig_y, self._screenshot.height() - 1))

        img = self._screenshot.toImage()
        self._selected_color = img.pixelColor(orig_x, orig_y)
        self.accept()

    def selected_color(self) -> QColor | None:
        """Retorna el QColor seleccionado, o None si se canceló."""
        return self._selected_color


# ---------------------------------------------------------------------------
# Main action dialog
# ---------------------------------------------------------------------------

class ActionDialog(QDialog):
    """
    Dialog for creating or editing a macro action.

    Presents fields for action name, click type, delays, error handling,
    and the ROI pixel coordinates. If ``roi_preset`` is provided, the ROI
    fields are pre-filled with those values.

    If ``screenshot`` is provided, a "Guardar ROI como PNG" button is shown
    that crops and saves the selected region. For ``verify_color`` actions,
    the same screenshot is used by the color picker.

    If ``actions_list`` is provided, the conditional branch target dropdowns
    are populated with the available action names.
    """

    def __init__(
        self,
        parent=None,
        roi_preset: dict | None = None,
        screenshot: QPixmap | None = None,
        actions_list: list[dict] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar Acción")
        self._roi_preset = roi_preset
        self._screenshot = screenshot
        self._actions_list = actions_list or []
        # verify_color state
        self._target_color: list[int] = [0, 0, 0]
        self._color_picked: bool = False
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
        self._click_type.addItems([
            "single", "double", "long_press",
            "verify_image", "conditional", "verify_color",
        ])
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

        # --- Verify image section (shared with conditional) ---
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

        # --- Conditional branch section (shared with verify_color) ---
        self._conditional_group = QGroupBox("Ramificación condicional")
        cond_form = QFormLayout(self._conditional_group)

        self._on_found_combo = QComboBox()
        self._on_found_combo.addItems(_BRANCH_LABELS)
        self._on_found_combo.currentIndexChanged.connect(
            lambda idx: self._on_branch_changed(idx, self._on_found_target)
        )
        cond_form.addRow("Si se encuentra:", self._on_found_combo)

        self._on_found_target = QComboBox()
        self._populate_target_combo(self._on_found_target)
        cond_form.addRow("→ Acción destino:", self._on_found_target)

        self._on_not_found_combo = QComboBox()
        self._on_not_found_combo.addItems(_BRANCH_LABELS)
        self._on_not_found_combo.setCurrentIndex(2)  # default: "Detener"
        self._on_not_found_combo.currentIndexChanged.connect(
            lambda idx: self._on_branch_changed(idx, self._on_not_found_target)
        )
        cond_form.addRow("Si NO se encuentra:", self._on_not_found_combo)

        self._on_not_found_target = QComboBox()
        self._populate_target_combo(self._on_not_found_target)
        cond_form.addRow("→ Acción destino:", self._on_not_found_target)

        main_layout.addWidget(self._conditional_group)

        # --- Verify color section ---
        self._verify_color_group = QGroupBox("Verificación de color")
        vc_form = QFormLayout(self._verify_color_group)

        # Color swatch + RGB text + pick button
        color_row = QHBoxLayout()
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(40, 22)
        self._color_swatch.setStyleSheet(
            "background-color: rgb(0,0,0); border: 1px solid #888;"
        )
        self._color_rgb_label = QLabel("(0, 0, 0)")
        self._btn_pick_color = QPushButton("Seleccionar color…")
        self._btn_pick_color.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_swatch)
        color_row.addWidget(self._color_rgb_label)
        color_row.addStretch()
        color_row.addWidget(self._btn_pick_color)
        vc_form.addRow("Color objetivo:", color_row)

        self._color_tolerance = QSpinBox()
        self._color_tolerance.setRange(0, 255)
        self._color_tolerance.setValue(30)
        self._color_tolerance.setToolTip(
            "Diferencia máxima permitida por canal (R, G, B). "
            "0 = coincidencia exacta."
        )
        vc_form.addRow("Tolerancia (0-255):", self._color_tolerance)

        self._min_ratio = QDoubleSpinBox()
        self._min_ratio.setRange(0.0, 1.0)
        self._min_ratio.setSingleStep(0.01)
        self._min_ratio.setDecimals(3)
        self._min_ratio.setValue(0.05)
        self._min_ratio.setToolTip(
            "Proporción mínima de píxeles del ROI que deben coincidir "
            "con el color (0.05 = 5 %)."
        )
        vc_form.addRow("Proporción mínima:", self._min_ratio)

        self._vc_max_retries = QSpinBox()
        self._vc_max_retries.setRange(0, 20)
        self._vc_max_retries.setValue(5)
        vc_form.addRow("Máx. reintentos:", self._vc_max_retries)

        self._vc_retry_delay_ms = QSpinBox()
        self._vc_retry_delay_ms.setRange(0, 10000)
        self._vc_retry_delay_ms.setSuffix(" ms")
        self._vc_retry_delay_ms.setValue(1000)
        vc_form.addRow("Delay reintento:", self._vc_retry_delay_ms)

        main_layout.addWidget(self._verify_color_group)

        # --- Save PNG button ---
        save_row = QHBoxLayout()
        self._btn_save_png = QPushButton("Guardar ROI como PNG…")
        self._btn_save_png.clicked.connect(self._save_roi_png)
        save_row.addStretch()
        save_row.addWidget(self._btn_save_png)
        main_layout.addLayout(save_row)

        # Configure initial visibility
        self._on_click_type_changed(self._click_type.currentText())

        # --- Button box ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _populate_target_combo(self, combo: QComboBox) -> None:
        """Fill a target QComboBox with the current actions_list."""
        combo.clear()
        for action in self._actions_list:
            label = f"{action.get('name', '?')}  [{action.get('id', '')}]"
            combo.addItem(label, userData=action.get("id", ""))
        combo.setVisible(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_click_type_changed(self, text: str) -> None:
        """Show/hide groups based on click_type."""
        is_verify = text == "verify_image"
        is_conditional = text == "conditional"
        is_verify_color = text == "verify_color"

        self._verify_group.setVisible(is_verify or is_conditional)
        self._conditional_group.setVisible(is_conditional or is_verify_color)
        self._verify_color_group.setVisible(is_verify_color)
        # Save PNG button: solo para tipos basados en imagen
        self._btn_save_png.setVisible(
            self._screenshot is not None and (is_verify or is_conditional)
        )

        # Sync target combo visibility
        if is_conditional or is_verify_color:
            self._on_branch_changed(
                self._on_found_combo.currentIndex(), self._on_found_target
            )
            self._on_branch_changed(
                self._on_not_found_combo.currentIndex(), self._on_not_found_target
            )

    def _on_branch_changed(self, index: int, target_combo: QComboBox) -> None:
        """Show/hide the target combo based on whether 'goto' is selected."""
        target_combo.setVisible(_BRANCH_VALUES[index] == "goto")

    # ------------------------------------------------------------------
    # Color picker
    # ------------------------------------------------------------------

    def _pick_color(self) -> None:
        """Abre ColorPickerDialog y aplica el color seleccionado."""
        if self._screenshot is None:
            QMessageBox.information(
                self,
                "Sin captura",
                "Primero carga una captura de pantalla para poder seleccionar un color.",
            )
            return
        dlg = ColorPickerDialog(self._screenshot, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            color = dlg.selected_color()
            if color is not None:
                self._target_color = [color.red(), color.green(), color.blue()]
                self._color_picked = True
                self._update_color_ui()

    def _update_color_ui(self) -> None:
        """Actualiza el swatch y la etiqueta RGB con el color actual."""
        r, g, b = self._target_color
        self._color_swatch.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #888;"
        )
        self._color_rgb_label.setText(f"({r}, {g}, {b})")

    # ------------------------------------------------------------------
    # Save PNG
    # ------------------------------------------------------------------

    def _save_roi_png(self) -> None:
        """Crop the current ROI from the screenshot and save as PNG."""
        if self._screenshot is None:
            return

        x = self._roi_x.value()
        y = self._roi_y.value()
        w = self._roi_w.value()
        h = self._roi_h.value()
        cropped = self._screenshot.copy(x, y, w, h)

        ct = self._click_type.currentText()
        if ct in ("verify_image", "conditional"):
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
            if ct in ("verify_image", "conditional"):
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

    def prefill_action(self, action: dict) -> None:
        """Populate all fields from an existing action dict (used when editing)."""
        ct = action.get("click_type", "single")
        idx = self._click_type.findText(ct)
        if idx >= 0:
            self._click_type.setCurrentIndex(idx)

        self._name.setText(action.get("name", ""))
        self._delay_before.setValue(action.get("delay_before", 0))
        self._delay_after.setValue(action.get("delay_after", 0))
        err_idx = self._on_error.findText(action.get("on_error", "stop"))
        if err_idx >= 0:
            self._on_error.setCurrentIndex(err_idx)

        if ct in ("verify_image", "conditional"):
            self._template_path_edit.setText(action.get("template_path", ""))
            self._threshold.setValue(float(action.get("threshold", 0.8)))
            self._max_retries.setValue(int(action.get("max_retries", 5)))
            self._retry_delay_ms.setValue(int(action.get("retry_delay_ms", 1000)))

        if ct in ("conditional", "verify_color"):
            self._set_branch_combo(
                self._on_found_combo,
                self._on_found_target,
                action.get("on_found", "next"),
                action.get("on_found_target_id"),
            )
            self._set_branch_combo(
                self._on_not_found_combo,
                self._on_not_found_target,
                action.get("on_not_found", "stop"),
                action.get("on_not_found_target_id"),
            )

        if ct == "verify_color":
            raw = action.get("target_color", [0, 0, 0])
            if isinstance(raw, (list, tuple)) and len(raw) == 3:
                self._target_color = [int(c) for c in raw]
                self._color_picked = True
                self._update_color_ui()
            self._color_tolerance.setValue(int(action.get("color_tolerance", 30)))
            self._min_ratio.setValue(float(action.get("min_ratio", 0.05)))
            self._vc_max_retries.setValue(int(action.get("max_retries", 5)))
            self._vc_retry_delay_ms.setValue(int(action.get("retry_delay_ms", 1000)))

    def _set_branch_combo(
        self,
        combo: QComboBox,
        target: QComboBox,
        value: str,
        target_id: str | None,
    ) -> None:
        """Select the right index in a branch combo and its target combo."""
        val_idx = _BRANCH_VALUES.index(value) if value in _BRANCH_VALUES else 0
        combo.setCurrentIndex(val_idx)
        if value == "goto" and target_id:
            for i in range(target.count()):
                if target.itemData(i) == target_id:
                    target.setCurrentIndex(i)
                    break

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_and_accept(self) -> None:
        """Validate inputs before closing with Accepted result."""
        if not self._name.text().strip():
            self._name.setFocus()
            self._name.setPlaceholderText("Ingresa un nombre")
            return

        ct = self._click_type.currentText()

        if ct in ("verify_image", "conditional"):
            if not self._template_path_edit.text().strip():
                QMessageBox.warning(
                    self,
                    "Template requerido",
                    "Guarda el ROI como PNG antes de confirmar.",
                )
                return

        if ct == "verify_color":
            if not self._color_picked:
                QMessageBox.warning(
                    self,
                    "Color no seleccionado",
                    "Haz clic en 'Seleccionar color…' para elegir el color objetivo.",
                )
                return

        if ct in ("conditional", "verify_color"):
            if _BRANCH_VALUES[self._on_found_combo.currentIndex()] == "goto":
                if self._on_found_target.count() == 0:
                    QMessageBox.warning(
                        self,
                        "Sin acciones disponibles",
                        "No hay acciones a las que saltar para 'Si se encuentra'.",
                    )
                    return
            if _BRANCH_VALUES[self._on_not_found_combo.currentIndex()] == "goto":
                if self._on_not_found_target.count() == 0:
                    QMessageBox.warning(
                        self,
                        "Sin acciones disponibles",
                        "No hay acciones a las que saltar para 'Si NO se encuentra'.",
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

        ct = data["click_type"]

        if ct == "verify_image":
            data["template_path"] = self._template_path_edit.text().strip()
            data["threshold"] = self._threshold.value()
            data["max_retries"] = self._max_retries.value()
            data["retry_delay_ms"] = self._retry_delay_ms.value()

        if ct == "conditional":
            data["template_path"] = self._template_path_edit.text().strip()
            data["threshold"] = self._threshold.value()
            data["max_retries"] = self._max_retries.value()
            data["retry_delay_ms"] = self._retry_delay_ms.value()

            on_found = _BRANCH_VALUES[self._on_found_combo.currentIndex()]
            data["on_found"] = on_found
            data["on_found_target_id"] = (
                self._on_found_target.currentData()
                if on_found == "goto" and self._on_found_target.count() > 0
                else None
            )

            on_not_found = _BRANCH_VALUES[self._on_not_found_combo.currentIndex()]
            data["on_not_found"] = on_not_found
            data["on_not_found_target_id"] = (
                self._on_not_found_target.currentData()
                if on_not_found == "goto" and self._on_not_found_target.count() > 0
                else None
            )

        if ct == "verify_color":
            data["target_color"] = list(self._target_color)
            data["color_tolerance"] = self._color_tolerance.value()
            data["min_ratio"] = self._min_ratio.value()
            data["max_retries"] = self._vc_max_retries.value()
            data["retry_delay_ms"] = self._vc_retry_delay_ms.value()

            on_found = _BRANCH_VALUES[self._on_found_combo.currentIndex()]
            data["on_found"] = on_found
            data["on_found_target_id"] = (
                self._on_found_target.currentData()
                if on_found == "goto" and self._on_found_target.count() > 0
                else None
            )

            on_not_found = _BRANCH_VALUES[self._on_not_found_combo.currentIndex()]
            data["on_not_found"] = on_not_found
            data["on_not_found_target_id"] = (
                self._on_not_found_target.currentData()
                if on_not_found == "goto" and self._on_not_found_target.count() > 0
                else None
            )

        return data
