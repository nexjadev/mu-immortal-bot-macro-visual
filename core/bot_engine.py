"""
core/bot_engine.py
==================
Execution engine for the mu-immortal-bot-macro-visual project.

Iterates over a loaded list of action dicts, dispatching ADB input commands
according to each action's configuration.  Threading is the Orchestrator's
responsibility; BotEngine.start() runs in the calling thread.
"""

import threading
import time
from random import randint
from typing import Callable, Optional

from core.adb_controller import ADBConnectionError, ADBController
from core.logger import BotLogger


class BotEngine:
    """
    Executes a sequence of macro actions against an Android emulator via ADB.

    The engine is intentionally single-threaded from its own perspective:
    start() blocks until the run loop finishes.  The Orchestrator is
    responsible for launching start() in a background thread when needed.

    Attributes:
        on_cycle_complete: Optional callback invoked after every complete cycle.
                           Receives the current cycle number (1-based) as its
                           only argument.
        on_error: Optional callback invoked when a critical (loop-stopping)
                  error occurs.  Receives the exception instance.
    """

    def __init__(self, adb: ADBController, logger: BotLogger) -> None:
        """
        Initialise the engine.

        Args:
            adb:    Configured ADBController instance used to send input events.
            logger: BotLogger instance for all log output.
        """
        self._adb: ADBController = adb
        self._logger: BotLogger = logger
        self._actions: list[dict] = []
        self._stop_event: threading.Event = threading.Event()

        # Public callbacks — set by the Orchestrator after instantiation.
        self.on_cycle_complete: Optional[Callable[[int], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_actions(self, actions: list[dict]) -> None:
        """
        Replace the internal action list with the provided one.

        Args:
            actions: List of action dicts as produced by ScriptManager.
        """
        self._actions = actions

    def stop(self) -> None:
        """
        Signal the run loop to exit cleanly at the next iteration boundary.

        Safe to call from any thread at any time.
        """
        self._stop_event.set()

    def start(self, cycles: int = 0) -> None:
        """
        Run the bot execution loop in the calling thread.

        Args:
            cycles: Number of full cycles to execute.  ``0`` means run
                    indefinitely until stop() is called.

        The loop:
        1. Iterates over enabled actions only.
        2. For each action, calculates a random coordinate within the ROI,
           waits delay_before, dispatches the ADB click, then waits delay_after.
        3. After a complete cycle, increments the cycle counter and calls
           on_cycle_complete if set.
        4. Checks the stop event at the start of every action iteration.

        Error semantics:
        - ADBConnectionError is always fatal — the loop stops, on_error fires.
        - Generic Exception with ``on_error='skip'`` logs a WARNING and
          continues to the next action.
        - Generic Exception with any other on_error value is fatal — same as
          ADBConnectionError.
        """
        # Clear any previously set stop signal before entering the loop.
        self._stop_event.clear()

        cycle: int = 0

        while not self._stop_event.is_set():
            # Honour finite-cycle limit.
            if cycles > 0 and cycle >= cycles:
                break

            # Flag set inside the inner loop to propagate an abort to the outer.
            _abort: bool = False

            for action in self._actions:
                # Check stop signal at the top of every action iteration.
                if self._stop_event.is_set():
                    break

                # Skip disabled actions.
                if not action.get("enabled", True):
                    continue

                name: str = action.get("name", "")
                roi: dict = action["roi"]
                click_type: str = action.get("click_type", "single")
                delay_before: int = action.get("delay_before", 0)
                delay_after: int = action.get("delay_after", 0)
                on_error_field: str = action.get("on_error", "stop")

                # Random coordinate within the ROI rectangle.
                # max(..., 0) guards against w=0 or h=0 edge cases.
                x: int = roi["x"] + randint(0, max(roi["w"] - 1, 0))
                y: int = roi["y"] + randint(0, max(roi["h"] - 1, 0))

                try:
                    # Pre-click delay (skip sleep when zero to avoid overhead).
                    if delay_before > 0:
                        time.sleep(delay_before / 1000)

                    # Dispatch the appropriate ADB input command.
                    if click_type == "single":
                        self._adb.tap(x, y)
                    elif click_type == "double":
                        self._adb.double_tap(x, y)
                    elif click_type == "long_press":
                        self._adb.long_press(x, y)

                    # Post-click delay.
                    if delay_after > 0:
                        time.sleep(delay_after / 1000)

                    # Log the action at the custom ACTION level.
                    self._logger.action(name, roi, x, y)

                except ADBConnectionError as exc:
                    # ADB connection loss is always fatal regardless of on_error.
                    self._logger.error(
                        f"ADB connection lost on action '{name}'", exc=exc
                    )
                    if self.on_error is not None:
                        self.on_error(exc)
                    self._stop_event.set()
                    _abort = True
                    break

                except Exception as exc:  # noqa: BLE001
                    if on_error_field == "skip":
                        # Non-fatal: warn and move on to the next action.
                        self._logger.warn(
                            f"Action '{name}' failed (skip): {exc}"
                        )
                        continue
                    else:
                        # Fatal: stop the loop and notify the caller.
                        self._logger.error(
                            f"Unhandled error on action '{name}'", exc=exc
                        )
                        if self.on_error is not None:
                            self.on_error(exc)
                        self._stop_event.set()
                        _abort = True
                        break

            # Propagate inner abort to the outer while-loop.
            if _abort:
                break

            cycle += 1

            if self.on_cycle_complete is not None:
                self.on_cycle_complete(cycle)
