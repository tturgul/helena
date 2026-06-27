"""Application entry point: build the QApplication and run the event loop.

Concepts:

* **QApplication**: every Qt GUI app needs exactly one. It owns the *event loop*
  — the loop that waits for user input (clicks, keys) and dispatches it to your
  widgets. Nothing is shown and no signal fires until ``app.exec()`` runs.
* **App metadata**: setting the application and organization names makes
  ``QStandardPaths`` resolve a stable per-app data folder (see ``storage.py``).
"""

import sys

from PySide6.QtWidgets import QApplication

from helena.ui.main_window import MainWindow


def run() -> int:
    """Create the app, show the main window, and start the event loop."""
    app = QApplication(sys.argv)

    # These two names drive where QStandardPaths puts our data file.
    app.setApplicationName("Helena")
    app.setOrganizationName("Helena")

    window = MainWindow()
    window.show()

    # exec() blocks here, running the event loop until the app quits. Its
    # return value becomes the process exit code.
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
