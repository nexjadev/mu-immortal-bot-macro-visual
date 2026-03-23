---
name: UI Architecture & Signal Contracts
description: Widget hierarchy, signal flow, and import rules for the mu-immortal-bot-macro-visual ui/ package
type: project
---

The ui/ package has four implementation files and an __init__.py.

Import chain (only these cross-module imports are allowed within ui/):
- main_window.py imports ROICanvas and ActionPanel
- roi_canvas.py imports ActionDialog from dialogs.py
- No ui/ file ever imports from core/

Widget hierarchy:
- MainWindow(QMainWindow)
  - QToolBar "Principal" (new / open / save actions + status label)
  - QSplitter(Horizontal) as central widget
    - ROICanvas(QLabel) — left, stretch factor 1
    - ActionPanel(QWidget) — right, fixedWidth 280, stretch factor 0
  - QStatusBar

Signal contracts:

MainWindow outward signals (Orchestrator connects to these):
  on_connect(str, int, str)   — host, port, window_title
  on_start(int, int)          — cycles, cycle_delay_ms
  on_stop()
  on_save(str)                — absolute file path
  on_load(str)                — absolute file path

ActionPanel outward signals:
  connect_requested(str, int, str)
  action_toggled(str, bool)       — id, enabled
  action_reordered(list)          — ordered list of ids
  start_requested(int, int)
  stop_requested()

ROICanvas outward signals:
  roi_created(dict)    — full action dict (id, name, click_type, delay_before, delay_after, on_error, roi, enabled)
  roi_edited(str, dict) — (action_id, updated_data_dict)
  roi_deleted(str)     — action_id

Internal flow: ROICanvas signals → MainWindow._on_roi_* slots → MainWindow.set_rois() → syncs both canvas and panel.

**Why:** The Orchestrator must connect to MainWindow's outward signals after constructing the window. The panel and canvas never know about core/.

**How to apply:** Never add core/ imports to ui/ files. Add new cross-component communication as pyqtSignal, never as direct method calls across the canvas/panel boundary.
