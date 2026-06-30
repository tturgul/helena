"""A modal dialog for naming a todo list (used for both create and rename).

This is the single-field sibling of ``AddTaskDialog``: a list only needs a
title, so there is no notes area. The same dialog serves two flows — creating a
new list and renaming an existing one — by accepting an initial title and a
window-title label.

PySide6 concepts here mirror ``AddTaskDialog``:

* **QDialog.exec()** shows the dialog modally and returns Accepted / Rejected.
* **QDialogButtonBox** supplies platform-correct OK/Cancel buttons; we keep a
  handle on OK so we can disable it until a title is entered.
"""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class AddListDialog(QDialog):
    """Collect a title for a new (or renamed) todo list."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title_text: str = "",
        window_title: str = "Add List",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(window_title)

        # Single-line title field. ``title_text`` pre-fills it (used when
        # renaming); the grey placeholder hints at the field while it's empty.
        self.title_edit = QLineEdit(title_text)
        self.title_edit.setPlaceholderText("List title")

        # OK / Cancel. A list needs a title, so OK is gated on non-empty input.
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title_edit)
        layout.addWidget(self.buttons)

        # Enable OK only while a non-empty title is present; Return confirms.
        self.title_edit.textChanged.connect(self._update_ok_enabled)
        self.title_edit.returnPressed.connect(self._try_accept)
        # Run once now so a pre-filled rename starts with OK already enabled.
        self._update_ok_enabled()

        self.title_edit.setFocus()
        self.title_edit.selectAll()  # ready to overwrite when renaming

    def _update_ok_enabled(self) -> None:
        """Enable OK only when a non-empty title has been entered."""
        self._ok_button.setEnabled(bool(self.title_edit.text().strip()))

    def _try_accept(self) -> None:
        """Accept the dialog, but only if a valid title is present."""
        if self.title_edit.text().strip():
            self.accept()

    def title(self) -> str:
        """Return the entered title, trimmed of surrounding whitespace."""
        return self.title_edit.text().strip()
