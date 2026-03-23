---
name: Project architecture and module interfaces
description: Confirmed method signatures, exception classes, and conventions discovered across all core modules during Orchestrator implementation
type: project
---

## ADBController (`core/adb_controller.py`)
- Constructor: `ADBController(host="127.0.0.1", port=5555)`
- Public attributes set at runtime: `host`, `port`
- `connect()` → None — raises `ADBConnectionError` on failure
- `get_resolution()` → `(width: int, height: int)` — raises `ADBCommandError`
- `tap(x, y)`, `double_tap(x, y)`, `long_press(x, y, duration_ms=1000)`
- `screenshot()` → `PIL.Image.Image` — raises `ADBCommandError` or `ADBConnectionError`
- `disconnect()` → None (errors suppressed)
- `is_connected()` → bool (live check via `get-state`)
- Exceptions: `ADBCommandError(command, stderr)`, `ADBConnectionError(msg)`

## BotEngine (`core/bot_engine.py`)
- Constructor: `BotEngine(adb: ADBController, logger: BotLogger)`
- `load_actions(actions: list[dict])` — replaces internal action list
- `start(cycles: int = 0)` — BLOCKING, runs in the calling thread
- `stop()` — sets threading.Event, safe from any thread
- Public callbacks (set by Orchestrator after construction):
  - `on_cycle_complete: Optional[Callable[[int], None]]` — receives 1-based cycle number
  - `on_error: Optional[Callable[[Exception], None]]` — receives the exception

## BotLogger (`core/logger.py`)
- Constructor: `BotLogger()` — no arguments
- `start_session(script_name: str, resolution: dict, cycles: int)` — opens log file
- `end_session(cycles_completed: int, status: str)` — closes log file
- `info(msg)`, `warn(msg)`, `debug(msg)`, `error(msg, exc: Exception = None)`
- `action(name, roi, tap_x, tap_y)` — logs at custom ACTION level (25)
- Module-level singleton: `logger = BotLogger()` (Orchestrator creates its own instance)

## ScriptManager (`core/script_manager.py`)
- Constructor: `ScriptManager()` — no arguments
- `load(path: str)` → validated dict — raises `ScriptNotFoundError`, `ScriptValidationError`
- `save(script: dict, path: str)` — updates `meta.created_at` before write
- `validate(script: dict)` — raises `ScriptValidationError` on first violation
- Exceptions: `ScriptNotFoundError(path)`, `ScriptValidationError(field, msg)`
- Profile methods: `load_profiles()`, `save_profile(profile)`, `delete_profile(name)`

## MainWindow (`ui/main_window.py`)
- Signals: `on_connect(str, int, str)`, `on_start(int, int)`, `on_stop()`, `on_save(str)`, `on_load(str)`
- Public methods: `set_screenshot(QPixmap)`, `set_rois(list)`, `set_state(str)`
- Valid states for `set_state`: `"disconnected"`, `"connected"`, `"running"`, `"error"`
- `closeEvent` emits `on_stop` automatically

## Script JSON schema (key fields)
```json
{
  "meta": { "name": str, "resolution": {"width": int, "height": int}, "created_at": str, "version": str },
  "emulator": { "host": str, "port": int, "window_title": str },
  "actions": [{ "id": str, "name": str, "enabled": bool, "roi": {"x":int,"y":int,"w":int,"h":int},
                "click_type": "single|double|long_press", "delay_before": int, "delay_after": int, "on_error": str }],
  "cycle_delay": int
}
```

## Orchestrator state strings (defined and emitted in this session)
`"connecting"`, `"connected"`, `"running"`, `"stopped"`, `"error"`

**Why:** `MainWindow.set_state` only recognises `"disconnected"`, `"connected"`, `"running"`, `"error"`. The Orchestrator also emits `"connecting"` and `"stopped"` — the bridge passes them through and the window degrades gracefully (shows "Desconocido" for unknown states).

**How to apply:** If the UI needs to display `"connecting"` or `"stopped"`, add them to `_STATE_LABELS` in `main_window.py`.
