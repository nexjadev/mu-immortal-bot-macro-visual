import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

# Register custom ACTION level at module import time
ACTION_LEVEL = 25
logging.addLevelName(ACTION_LEVEL, "ACTION")

SEPARATOR = "=" * 80


class BotLogger:
    def __init__(self):
        self._logger = logging.getLogger("bot")
        self._logger.propagate = False
        self._file_handler = None
        self._log_path = None

    def start_session(self, script_name: str, resolution: dict, cycles: int):
        # Close and remove existing file handler if present
        if self._file_handler is not None:
            self._logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

        # Remove any existing handlers to avoid duplicates on repeated calls
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

        # Create logs directory if it does not exist
        Path("logs").mkdir(exist_ok=True)

        # Generate session log file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"logs/session_{timestamp}.log"
        self._log_path = log_path

        # Determine log level: DEBUG only when BOT_DEBUG=1, otherwise INFO
        if os.environ.get("BOT_DEBUG") == "1":
            level = logging.DEBUG
        else:
            level = logging.INFO

        self._logger.setLevel(level)

        # Create formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-7s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        self._logger.addHandler(file_handler)
        self._file_handler = file_handler

        # Stream handler (stdout)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(level)
        self._logger.addHandler(stream_handler)

        # Write session header directly to file
        started_at = datetime.now().isoformat(sep=" ", timespec="seconds")
        width = resolution.get("width", 0)
        height = resolution.get("height", 0)
        header = (
            f"{SEPARATOR}\n"
            f"SESSION START\n"
            f"Script    : {script_name}\n"
            f"Resolution: {width}x{height}\n"
            f"Max cycles: {cycles}\n"
            f"Started   : {started_at}\n"
            f"{SEPARATOR}\n"
            f"\n"
        )
        self._file_handler.stream.write(header)
        self._file_handler.stream.flush()

    def end_session(self, cycles_completed: int, status: str):
        if self._file_handler is None:
            return

        ended_at = datetime.now().isoformat(sep=" ", timespec="seconds")
        footer = (
            f"\n{SEPARATOR}\n"
            f"SESSION END\n"
            f"Cycles completed: {cycles_completed}\n"
            f"Status          : {status}\n"
            f"Ended           : {ended_at}\n"
            f"{SEPARATOR}\n"
        )
        self._file_handler.stream.write(footer)
        self._file_handler.stream.flush()

        self._logger.removeHandler(self._file_handler)
        self._file_handler.close()
        self._file_handler = None

    def info(self, msg: str):
        self._logger.info(msg)

    def warn(self, msg: str):
        self._logger.warning(msg)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def action(self, name: str, roi: dict, tap_x: int, tap_y: int):
        mensaje = (
            f"{name} | ROI({roi['x']},{roi['y']},{roi['w']},{roi['h']})"
            f" \u2192 tap({tap_x},{tap_y})"
        )
        self._logger.log(ACTION_LEVEL, mensaje)

    def error(self, msg: str, exc: Exception = None):
        if exc is None:
            self._logger.error(msg)
        else:
            self._logger.error(f"{msg}\n{traceback.format_exc()}")

    @property
    def log_path(self):
        return self._log_path


# Module-level singleton
logger = BotLogger()
