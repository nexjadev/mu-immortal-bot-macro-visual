---
name: logger.py implementation status
description: BotLogger implementation details and design decisions made during initial creation
type: project
---

core/logger.py and tests/test_logger.py were implemented in the first conversation (2026-03-22).

Key design decisions made:

- `logging.getLogger("bot")` is used as the internal logger name, with `propagate = False` to avoid root logger duplication.
- `start_session()` clears ALL existing handlers before adding new ones (file + stream), guaranteeing no duplicates across repeated calls.
- The ACTION level (25) is registered at module import time via `logging.addLevelName(25, "ACTION")`.
- Default log level when `BOT_DEBUG` is not set is `25` (ACTION), not INFO — so DEBUG and INFO messages are suppressed unless BOT_DEBUG=1.
- Session header and footer are written directly via `_file_handler.stream.write()`, bypassing the logging formatter, to produce clean separator blocks.
- The singleton `logger = BotLogger()` is at module bottom; consumers that need isolation (tests) instantiate `BotLogger()` directly.

**Why:** Spec required these behaviors explicitly, including the "no print()" rule and the dual-handler (file+stream) per session model.

**How to apply:** When extending logger.py, preserve the handler-clearing pattern in start_session and never reintroduce print() calls.
