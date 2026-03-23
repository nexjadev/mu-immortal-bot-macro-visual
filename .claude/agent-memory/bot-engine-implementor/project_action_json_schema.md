---
name: Action JSON schema fields and click_type values
description: Exact field names and allowed values for action dicts parsed from script JSON — critical for bot_engine loop correctness
type: project
---

Action dict fields (from CLAUDE.md and observed usage):
- "id": str
- "name": str
- "enabled": bool (default True when missing)
- "roi": dict with keys "x", "y", "w", "h" (all int)
- "click_type": str — allowed values: "single", "double", "long_press"
- "delay_before": int (milliseconds, 0 = no sleep)
- "delay_after": int (milliseconds, 0 = no sleep)
- "on_error": str — "skip" continues loop; anything else ("stop") halts it

IMPORTANT: click_type uses "single" (not "tap") and "double" (not "double_tap").
The string "long_press" matches the method name but click_type is still "long_press".

ROI coordinate calculation:
  x = roi["x"] + randint(0, max(roi["w"] - 1, 0))
  y = roi["y"] + randint(0, max(roi["h"] - 1, 0))
The max(..., 0) guards against w=0 or h=0 degenerate ROIs.

**Why:** Confirmed from CLAUDE.md JSON schema and test helper _make_action.
**How to apply:** Always use these field names verbatim. Never assume "tap" or "double_tap" as click_type values.
