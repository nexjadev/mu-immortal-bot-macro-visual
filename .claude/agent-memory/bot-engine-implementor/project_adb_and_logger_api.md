---
name: ADBController and BotLogger API signatures
description: Exact method signatures for ADBController and BotLogger as confirmed from source — critical for correct bot_engine.py implementation
type: project
---

ADBController (core/adb_controller.py):
- tap(x: int, y: int) -> None
- double_tap(x: int, y: int) -> None
- long_press(x: int, y: int, duration_ms: int = 1000) -> None
- ADBConnectionError — defined in same module, no message formatting required

BotLogger (core/logger.py):
- action(name: str, roi: dict, tap_x: int, tap_y: int) — logs at ACTION level (25)
- error(msg: str, exc: Exception = None) — includes traceback.format_exc() when exc is provided
- warn(msg: str) — maps to logging.WARNING
- info(msg: str)
- debug(msg: str)

ACTION level (25) is registered at logger.py module import time via logging.addLevelName(25, "ACTION").
bot_engine.py does NOT need to re-register it — importing BotLogger is sufficient.

**Why:** These were read directly from the implemented source files.
**How to apply:** Use these signatures exactly when calling logger/adb from BotEngine. Do not guess method names.
