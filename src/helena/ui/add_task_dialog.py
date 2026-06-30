"""A modal dialog for creating a new task (title + optional notes).

This mirrors the "add list" flow but offers two fields instead of one: a small
single-line title and a larger multi-line notes area. The notes are optional —
only a title is required.

New PySide6 concepts used here:

* **QDialog.exec()**: shows the dialog *modally* and returns ``Accepted`` or
  ``Rejected`` once the user closes it.
* **QDialogButtonBox**: supplies platform-correct OK/Cancel buttons; we keep a
  handle on the OK button so we can disable it until a title is entered.
* **QShortcut**: binds a key combination (Ctrl+Return) to "accept", so the user
  can confirm without leaving the notes field — where a plain Return inserts a
  new line rather than submitting.
"""

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AddTaskDialog(QDialog):
    """Collect a title and optional notes for a new task."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Task")

        # --- Title (small, single line) ----------------------------------
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Task title")

        # --- Notes (large, multi-line, optional) -------------------------
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Notes (optional)…")

        # --- OK / Cancel --------------------------------------------------
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        # A task needs a title, so OK stays disabled until one is typed.
        self._ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)

        # --- Lay everything out top to bottom ----------------------------
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title_edit)
        layout.addWidget(QLabel("Notes"))
        layout.addWidget(self.body_edit)
        layout.addWidget(self.buttons)

        # --- Interactions -------------------------------------------------
        # Enable OK only while the title has non-whitespace content.
        self.title_edit.textChanged.connect(self._update_ok_enabled)
        # Return in the title field confirms the dialog (when a title exists).
        self.title_edit.returnPressed.connect(self._try_accept)
        # Ctrl+Return confirms from anywhere — useful while typing notes, where a
        # plain Return inserts a newline instead of submitting.
        accept_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        accept_shortcut.activated.connect(self._try_accept)

        # Start focused in the title field so the user can type immediately.
        self.title_edit.setFocus()

    # ------------------------------------------------------------------
    def _update_ok_enabled(self) -> None:
        """Enable OK only when a non-empty title has been entered."""
        self._ok_button.setEnabled(bool(self.title_edit.text().strip()))

    def _try_accept(self) -> None:
        """Accept the dialog, but only if a valid title is present."""
        if self.title_edit.text().strip():
            self.accept()

    # ------------------------------------------------------------------
    # Accessors the caller reads once exec() returns Accepted.
    # ------------------------------------------------------------------
    def title(self) -> str:
        """Return the entered title, trimmed of surrounding whitespace."""
        return self.title_edit.text().strip()

    def body(self) -> str:
        """Return the entered notes (may be empty)."""
        return self.body_edit.toPlainText().strip()
