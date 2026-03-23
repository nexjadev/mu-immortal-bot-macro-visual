---
name: ROI / Action dict format used throughout ui/
description: The exact dict shape that ROICanvas emits and MainWindow stores as self._rois
type: project
---

Every item in self._rois (MainWindow) and self._rois (ROICanvas) has this shape:

{
    "id":          str,        # uuid4 hex[:8], set by ROICanvas on creation
    "name":        str,
    "click_type":  str,        # "single" | "double" | "long_press"
    "delay_before": int,       # ms
    "delay_after":  int,       # ms
    "on_error":    str,        # "stop" | "skip"
    "enabled":     bool,
    "roi": {
        "x": int,              # image-space pixels
        "y": int,
        "w": int,
        "h": int,
    }
}

ROICanvas._widget_rect() reads roi["roi"]["x/y/w/h"].
ActionPanel.set_actions() reads action["id"], action["name"], action["enabled"].
ActionDialog.get_data() returns this shape minus "id" and "enabled" (those are added by the caller).

**Why:** The shape mirrors the JSON script format in CLAUDE.md so that script_manager.py can persist it without transformation.

**How to apply:** When adding new action fields, add them to ActionDialog.get_data() and update this record. Always keep "roi" as a sub-dict, not flattened.
