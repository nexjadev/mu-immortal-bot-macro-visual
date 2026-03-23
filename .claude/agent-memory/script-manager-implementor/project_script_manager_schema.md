---
name: Script Manager Schema and API
description: Canonical schema for script JSON and ScriptManager method signatures, including deviations from system prompt spec
type: project
---

The implemented ScriptManager deviates from the system-prompt spec in two intentional ways that match the user's detailed instruction:

1. **Exception signatures differ from system-prompt defaults.**
   - `ScriptNotFoundError(path: str)` — stores `self.path`, message: `f"Script not found: {path}"`
   - `ScriptValidationError(field: str, msg: str)` — stores `self.field` and `self.msg`, message: `f"[{field}] {msg}"`
   - Both inherit from plain `Exception`, NOT `FileNotFoundError`/`ValueError`.

2. **`load()` and `save()` accept `path: str` as a positional argument** (not stored on the instance). The class has no constructor.

3. **`delete_profile()` returns `None`**, not `bool` — the user's spec did not require a return value (unlike the system-prompt spec which said return `bool`).

4. **`validate()` includes `on_error` field per action** — this is required by the user's spec but absent from the system-prompt spec's action field list.

**Validation order in `validate()`:**
1. Top-level keys: meta, emulator, actions, cycle_delay
2. meta.name (str, non-empty)
3. meta.resolution (dict, width int>0, height int>0)
4. meta.version (str)
5. emulator.host (str)
6. emulator.port (int, 1–65535)
7. emulator.window_title (str)
8. cycle_delay (int >= 0)
9. actions (list, non-empty)
10. Per-action: id, name, enabled (bool checked BEFORE int), roi dict, roi.x/y >= 0, roi.w/h > 0, click_type in set, delay_before/after >= 0, on_error str non-empty

**Why:** `bool` is a subclass of `int` in Python — checking `isinstance(v, bool)` before `isinstance(v, int)` prevents `True`/`False` from passing integer checks.

**How to apply:** Maintain this order in any future additions to validate(). Always guard numeric checks with the bool-first pattern.
