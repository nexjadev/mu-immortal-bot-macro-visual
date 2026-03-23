"""
main.py
=======
Application entry point for mu-immortal-bot-macro-visual.

Constructs the QApplication, MainWindow, and Orchestrator, then wires them
together through a thread-safe signal bridge before entering the Qt event loop.

Architecture notes:
- MainWindow emits Qt signals (on_connect, on_start, on_stop, on_load, on_save)
  which are connected directly to Orchestrator methods.
- The Orchestrator's on_state_change callback is routed through _StateBridge,
  which re-emits as a Qt signal so that window.set_state() is always invoked
  on the main (GUI) thread, regardless of which thread the Orchestrator calls
  the callback from.
"""

import io
import sys

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from core.orchestrator import Orchestrator
from ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Thread-safe state bridge
# ---------------------------------------------------------------------------

class _StateBridge(QObject):
    """Marshals Orchestrator state strings onto the Qt GUI thread.

    The Orchestrator's on_state_change callback may be invoked from a
    background daemon thread (e.g. the BotEngine thread).  Calling Qt
    widget methods directly from a non-GUI thread is unsafe.  This bridge
    converts the raw Python callback into a Qt signal emission, which Qt's
    event loop delivers on the correct thread automatically.

    Args:
        window: The MainWindow whose ``set_state`` method will be called.
    """

    state_changed = pyqtSignal(str)

    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.state_changed.connect(window.set_state)

    def notify(self, state: str) -> None:
        """Emit the state_changed signal (safe from any thread).

        Args:
            state: State string to forward to MainWindow.set_state.
        """
        self.state_changed.emit(state)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise the application and enter the Qt event loop."""
    app = QApplication(sys.argv)

    window = MainWindow()
    orchestrator = Orchestrator()
    bridge = _StateBridge(window)

    # Route Orchestrator state changes to the UI thread-safely.
    orchestrator.on_state_change = bridge.notify

    # Wire UI signals to Orchestrator methods.
    window.on_connect.connect(orchestrator.connect)
    window.on_start.connect(orchestrator.start_bot)
    window.on_stop.connect(orchestrator.stop_bot)
    window.on_load.connect(orchestrator.load_script)
    window.on_save.connect(orchestrator.save_script)
    window.on_actions_changed.connect(orchestrator.sync_actions)

    def _do_refresh() -> None:
        """Captura screenshot del emulador y actualiza el canvas."""
        img = orchestrator.get_screenshot()
        if img is None:
            return
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        window.set_screenshot(pixmap)

    window.on_refresh.connect(_do_refresh)

    # Set initial visual state.
    window.set_state("disconnected")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
