"""A small modal dialog for editing user preferences.

New PySide6 concepts:

* **QDialog**: a top-level window shown *modally* — ``exec()`` blocks the rest
  of the app until the dialog is closed, returning Accepted or Rejected.
* **QFormLayout**: arranges label/field pairs in two aligned columns — the
  conventional look for settings forms.
* **QDialogButtonBox**: provides platform-correct OK/Cancel buttons already
  wired to the dialog's ``accept()`` / ``reject()`` slots.

The dialog reads current values from ``settings.py`` and, on OK, saves them and
applies the font change live so the user sees it right away.
"""

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from helena import settings


class SettingsDialog(QDialog):
    """Edit application preferences (currently just the UI font size)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        # --- Font size field ---------------------------------------------
        # A spin box constrains input to whole numbers in a fixed range, so the
        # user can't type an invalid size.
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(settings.MIN_FONT_SIZE, settings.MAX_FONT_SIZE)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(settings.get_font_size())

        form = QFormLayout()
        form.addRow("Font size:", self.font_size_spin)

        # --- OK / Cancel --------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        """Save the chosen settings, apply them live, then close."""
        size = self.font_size_spin.value()
        settings.set_font_size(size)
        self._apply_font_size(size)
        self.accept()

    @staticmethod
    def _apply_font_size(size: int) -> None:
        """Update the whole application's font immediately.

        Setting the *application* font propagates to every widget that hasn't
        set its own font, so the change is visible without restarting.
        """
        app = QApplication.instance()
        if app is not None:
            font = app.font()
            font.setPointSize(size)
            app.setFont(font)
