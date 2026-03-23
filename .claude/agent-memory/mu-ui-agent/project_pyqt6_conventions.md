---
name: PyQt6 conventions used in this codebase
description: PyQt6-specific patterns, enum access style, and API choices applied throughout ui/
type: project
---

Enum access style (PyQt6, not PyQt5 short-form):
  Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
  Qt.MouseButton.LeftButton / RightButton
  Qt.CheckState.Checked / Unchecked
  Qt.ItemFlag.ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable | ItemIsDragEnabled
  Qt.ItemDataRole.UserRole
  Qt.DropAction.MoveAction
  Qt.Orientation.Horizontal
  QAbstractItemView.DragDropMode.InternalMove
  QRubberBand.Shape.Rectangle
  QSizePolicy.Policy.Expanding
  QDialog.DialogCode.Accepted
  QDialogButtonBox.StandardButton.Ok | Cancel
  QMessageBox.StandardButton.Yes | No
  QPainter.RenderHint.Antialiasing

Mouse global position (PyQt6):
  Use event.globalPosition().toPoint()   — NOT event.globalPos() (deprecated)

Dialog exec:
  Use dlg.exec()  — NOT dlg.exec_() (removed in PyQt6)

Item flags are combined with | (bitwise or), all from Qt.ItemFlag namespace.

_DIALOG_ACCEPTED is cached at module level in roi_canvas.py:
  _DIALOG_ACCEPTED = QDialog.DialogCode.Accepted

**Why:** PyQt6 removed short-form enums and exec_(); mixing styles causes AttributeError at runtime.
**How to apply:** Always use the full enum path. Run a quick grep for "exec_()" or ".globalPos()" if porting any PyQt5 snippet.
