"""Application entry point: build the QApplication and run the event loop.

Concepts:

* **QApplication**: every Qt GUI app needs exactly one. It owns the *event loop*
  — the loop that waits for user input (clicks, keys) and dispatches it to your
  widgets. Nothing is shown and no signal fires until ``app.exec()`` runs.
* **App metadata**: setting the application and organization names makes
  ``QStandardPaths`` (for todo data) and ``QSettings`` (for preferences) resolve
  stable per-app locations.
* **Application font**: a widget inherits the application font unless it sets its
  own, so setting it once here restyles the whole UI consistently.
"""

import sys

from PySide6.QtWidgets import QApplication

from helena import settings
from helena.ui.main_window import MainWindow


def run() -> int:
    """Create the app, show the main window, and start the event loop."""
    app = QApplication(sys.argv)

    # These two names drive where QStandardPaths and QSettings store data.
    # They must be set *before* we read any QSettings value below.
    app.setApplicationName("Helena")
    app.setOrganizationName("Helena")

    # Apply the user's preferred base font size application-wide. We start from
    # the current default font and change only its point size, keeping the
    # platform's native font family. The size comes from saved settings (or the
    # default on first run), and the Settings dialog can change it live.
    font = app.font()
    font.setPointSize(settings.get_font_size())
    app.setFont(font)

    window = MainWindow()
    window.show()

    # exec() blocks here, running the event loop until the app quits. Its
    # return value becomes the process exit code.
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
