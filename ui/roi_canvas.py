"""
ui/roi_canvas.py
Interactive canvas widget for visualizing and editing ROIs on a screenshot.
"""

import uuid

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMenu,
    QRubberBand,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPixmap

from ui.dialogs import ActionDialog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum drag distance (widget pixels) to register a new ROI.
_MIN_DRAG_PX: int = 5

# HSV palette: one colour per ROI, cycling every 37° of hue.
_PALETTE: list[QColor] = [QColor.fromHsv(h, 200, 220) for h in range(0, 360, 37)]

_DIALOG_ACCEPTED = QDialog.DialogCode.Accepted


class ROICanvas(QLabel):
    """
    Widget that displays a screenshot and lets the user draw, inspect,
    edit, and delete ROIs via mouse gestures and a context menu.

    Left-click drag  → draw a new ROI; on release, ActionDialog opens.
    Right-click on ROI → context menu with Edit / Delete.

    Signals
    -------
    roi_created(dict)
        Emitted when the user confirms a newly drawn ROI.
        The dict is a complete action record compatible with the JSON script
        format (id, name, click_type, delay_before, delay_after, on_error,
        roi, enabled).
    roi_edited(str, dict)
        Emitted when the user edits an existing ROI.
        Arguments: (action_id, updated_data_dict).
    roi_deleted(str)
        Emitted when the user deletes an ROI.
        Argument: action_id.
    """

    roi_created = pyqtSignal(dict)
    roi_edited = pyqtSignal(str, dict)
    roi_deleted = pyqtSignal(str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        self._rois: list[dict] = []
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._drag_origin: QPoint = QPoint()
        self._image_size: QSize = QSize(1280, 720)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_screenshot(self, pixmap: QPixmap) -> None:
        """
        Display *pixmap* as the canvas background and record its natural size
        so that ROI coordinates can be scaled correctly.
        """
        self.setPixmap(pixmap)
        self._image_size = pixmap.size()
        self.update()

    def set_rois(self, rois: list[dict]) -> None:
        """
        Replace the current ROI list and repaint the canvas.

        Parameters
        ----------
        rois:
            List of action dicts, each containing a ``roi`` sub-dict with
            keys x, y, w, h (image-space pixels).
        """
        self._rois = list(rois)
        self.update()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _scale_factor(self) -> tuple[float, float]:
        """
        Return (sx, sy) — the ratio of widget pixels to image pixels.

        Falls back to (1.0, 1.0) when no pixmap is loaded or the image
        dimensions are degenerate.
        """
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return (1.0, 1.0)
        iw = self._image_size.width()
        ih = self._image_size.height()
        if iw == 0 or ih == 0:
            return (1.0, 1.0)
        return (self.width() / iw, self.height() / ih)

    def _widget_rect(self, roi: dict) -> QRect:
        """
        Convert the ``roi`` sub-dict of an action to a QRect in widget
        coordinates.
        """
        sx, sy = self._scale_factor()
        r = roi["roi"]
        return QRect(
            int(r["x"] * sx),
            int(r["y"] * sy),
            int(r["w"] * sx),
            int(r["h"] * sy),
        )

    def _image_rect(self, widget_rect: QRect) -> dict:
        """
        Convert a QRect in widget coordinates back to an image-space ROI dict.
        """
        sx, sy = self._scale_factor()
        return {
            "x": int(widget_rect.x() / sx),
            "y": int(widget_rect.y() / sy),
            "w": max(1, int(widget_rect.width() / sx)),
            "h": max(1, int(widget_rect.height() / sy)),
        }

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        """Handle left-button drag start and right-button context menu."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.pos()
            self._rubber_band.setGeometry(QRect(self._drag_origin, QSize()))
            self._rubber_band.show()

        elif event.button() == Qt.MouseButton.RightButton:
            pos = event.pos()
            # Iterate reversed so the topmost (last drawn) ROI wins.
            for roi in reversed(self._rois):
                if self._widget_rect(roi).contains(pos):
                    self._show_context_menu(roi, event.globalPosition().toPoint())
                    break

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Stretch the rubber-band while the user drags."""
        if self._rubber_band.isVisible():
            self._rubber_band.setGeometry(
                QRect(self._drag_origin, event.pos()).normalized()
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Finalise the rubber-band selection and open ActionDialog."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._rubber_band.isVisible()
        ):
            self._rubber_band.hide()
            rect = QRect(self._drag_origin, event.pos()).normalized()

            # Ignore accidental clicks (drag too small).
            if rect.width() >= _MIN_DRAG_PX and rect.height() >= _MIN_DRAG_PX:
                roi_dict = self._image_rect(rect)
                dlg = ActionDialog(self, roi_preset=roi_dict)
                if dlg.exec() == _DIALOG_ACCEPTED:
                    data = dlg.get_data()
                    data["id"] = uuid.uuid4().hex[:8]
                    data["enabled"] = True
                    data["roi"] = roi_dict  # authoritative from canvas drag
                    self.roi_created.emit(data)

        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Draw the pixmap (via QLabel base) then overlay all ROI rectangles."""
        super().paintEvent(event)

        pm = self.pixmap()
        if pm is None or pm.isNull() or not self._rois:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Arial", 9))

        for i, roi in enumerate(self._rois):
            color = _PALETTE[i % len(_PALETTE)]
            pen = QPen(color, 2)
            painter.setPen(pen)
            rect = self._widget_rect(roi)
            painter.drawRect(rect)

            label_text = roi.get("name", "")
            if label_text:
                text_x = rect.x() + 3
                text_y = rect.y() + 13
                # Subtle shadow for legibility on varied backgrounds.
                painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
                painter.drawText(text_x + 1, text_y + 1, label_text)
                painter.setPen(pen)
                painter.drawText(text_x, text_y, label_text)

        painter.end()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, roi: dict, global_pos: QPoint) -> None:
        """Display an Edit / Delete context menu for the given ROI."""
        menu = QMenu(self)
        edit_action = menu.addAction("Editar")
        del_action = menu.addAction("Borrar")
        chosen = menu.exec(global_pos)

        if chosen == edit_action:
            self._edit_roi(roi)
        elif chosen == del_action:
            self.roi_deleted.emit(roi["id"])

    def _edit_roi(self, roi: dict) -> None:
        """Open ActionDialog pre-filled with *roi*'s current values."""
        dlg = ActionDialog(self, roi_preset=roi.get("roi"))

        # Pre-fill action fields from the existing action dict.
        dlg._name.setText(roi.get("name", ""))

        idx = dlg._click_type.findText(roi.get("click_type", "single"))
        if idx >= 0:
            dlg._click_type.setCurrentIndex(idx)

        dlg._delay_before.setValue(roi.get("delay_before", 0))
        dlg._delay_after.setValue(roi.get("delay_after", 0))

        idx2 = dlg._on_error.findText(roi.get("on_error", "stop"))
        if idx2 >= 0:
            dlg._on_error.setCurrentIndex(idx2)

        if dlg.exec() == _DIALOG_ACCEPTED:
            self.roi_edited.emit(roi["id"], dlg.get_data())
