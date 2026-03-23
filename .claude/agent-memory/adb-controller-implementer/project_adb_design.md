---
name: ADB controller design decisions
description: Key implementation choices made in core/adb_controller.py — constructor signature, logger name, subprocess patterns, and test patching path
type: project
---

Constructor uses `host: str, port: int` instead of the spec's `device_id: str = None`.
The project's JSON config stores `"host"` and `"port"` separately (see CLAUDE.md emulator block),
so the constructor was adapted to match that shape from the start.

**Why:** Avoids a translation layer in orchestrator.py when reading profiles.json.
**How to apply:** When other modules call ADBController, pass `host=` and `port=` kwargs, not a combined serial string.

Logger name is `"bot.adb"` (not `__name__` / `"core.adb_controller"`).
**Why:** The project uses a centralised `BotLogger` hierarchy; child loggers under `"bot.*"` inherit its handlers automatically.
**How to apply:** All log calls inside adb_controller.py use `self._logger` which is `logging.getLogger("bot.adb")`.

`_run()` is the single internal subprocess helper for all commands except `connect()`, `screenshot()`, and `disconnect()`.
Those three own their subprocess.run call directly because they need different argument shapes or binary output.

`double_tap()` calls `_run()` twice with no artificial sleep — the ADB round-trip latency is sufficient for the emulator.

`screenshot()` uses `timeout=10` (not the default 5) because screencap can be slow on heavier emulators.

Disconnect errors are swallowed intentionally — `_connected` is always reset to False regardless.

Test patch target is `core.adb_controller.subprocess.run` (not `subprocess.run`).
This is the only correct path because the module imports `subprocess` at module level.
