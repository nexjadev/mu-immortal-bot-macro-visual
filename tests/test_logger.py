import os
import unittest
from pathlib import Path

from core.logger import BotLogger


class TestBotLogger(unittest.TestCase):

    def setUp(self):
        self.logger = BotLogger()

    def tearDown(self):
        # End session if active, ignore errors
        try:
            if self.logger._file_handler is not None:
                self.logger.end_session(0, "teardown")
        except Exception:
            pass
        # Remove log file if it was created
        try:
            if self.logger.log_path and Path(self.logger.log_path).exists():
                Path(self.logger.log_path).unlink()
        except Exception:
            pass

    def _start(self, script="test_script", width=1280, height=720, cycles=10):
        self.logger.start_session(script, {"width": width, "height": height}, cycles)

    def _read_log(self):
        return Path(self.logger.log_path).read_text(encoding="utf-8")

    # 1. Session file is created on disk
    def test_session_file_created(self):
        self._start()
        self.assertIsNotNone(self.logger.log_path)
        self.assertTrue(Path(self.logger.log_path).is_file())

    # 2. Header is written to the file
    def test_header_in_file(self):
        self._start()
        content = self._read_log()
        self.assertIn("=" * 80, content)
        self.assertIn("SESSION START", content)

    # 3. Footer is written after end_session
    def test_footer_in_file(self):
        self._start()
        self.logger.end_session(5, "OK")
        content = self._read_log()
        self.assertIn("SESSION END", content)
        self.assertIn("Status", content)

    # 4. info() message appears in file
    def test_info_logged(self):
        self._start()
        self.logger.info("mensaje info")
        content = self._read_log()
        self.assertIn("mensaje info", content)

    # 5. warn() message appears in file
    def test_warn_logged(self):
        self._start()
        self.logger.warn("aviso")
        content = self._read_log()
        self.assertIn("aviso", content)

    # 6. action() produces correct ROI and tap format
    def test_action_format(self):
        self._start()
        self.logger.action(
            "ClickBoton", {"x": 10, "y": 20, "w": 100, "h": 50}, 60, 45
        )
        content = self._read_log()
        self.assertIn("ROI(10,20,100,50)", content)
        self.assertIn("tap(60,45)", content)

    # 7. error() with exception includes traceback
    def test_error_with_traceback(self):
        self._start()
        try:
            raise ValueError("boom")
        except ValueError as e:
            self.logger.error("Error ocurrido", exc=e)
        content = self._read_log()
        self.assertIn("Traceback", content)

    # 8. debug() is hidden when BOT_DEBUG is not set
    def test_debug_hidden_by_default(self):
        # Ensure BOT_DEBUG is not active
        os.environ.pop("BOT_DEBUG", None)
        self._start()
        self.logger.debug("secreto")
        content = self._read_log()
        self.assertNotIn("secreto", content)

    # 9. Starting a new session does not leave duplicate handlers
    def test_new_session_closes_previous(self):
        self._start(script="first")
        self._start(script="second")
        # At most 2 handlers: 1 FileHandler + 1 StreamHandler
        self.assertLessEqual(len(self.logger._logger.handlers), 2)


if __name__ == "__main__":
    unittest.main()
