"""A modal dialog for editing user preferences.

New PySide6 concepts:

* **QDialog**: a top-level window shown *modally* — ``exec()`` blocks the rest
  of the app until the dialog is closed, returning Accepted or Rejected.
* **QGroupBox**: a titled frame that visually groups related controls, keeping a
  multi-section form readable.
* **QFormLayout**: arranges label/field pairs in two aligned columns.
* **QDialogButtonBox**: provides platform-correct OK/Cancel buttons.
* **QFileDialog.getExistingDirectory**: the native "choose a folder" picker.
* **QMessageBox.question**: a native Yes/No prompt, used to confirm what should
  happen to existing data when the storage location changes.

The dialog reads current values from ``settings`` and, on OK, saves them. Font
and theme are applied live so the change is visible immediately; a change to the
data folder is validated and, if requested, the existing data is moved.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from helena import settings, storage, theme


class SettingsDialog(QDialog):
    """Edit application preferences: appearance, plus data location & backups."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        # ===== Appearance =================================================
        # A spin box constrains the font size to whole numbers in a fixed range.
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(settings.MIN_FONT_SIZE, settings.MAX_FONT_SIZE)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(settings.get_font_size())

        # Each theme entry stores its settings value as item *data*, so the code
        # doesn't depend on the visible label text.
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System", settings.THEME_SYSTEM)
        self.theme_combo.addItem("Light", settings.THEME_LIGHT)
        self.theme_combo.addItem("Dark", settings.THEME_DARK)
        current_theme = self.theme_combo.findData(settings.get_theme())
        if current_theme >= 0:
            self.theme_combo.setCurrentIndex(current_theme)

        appearance_form = QFormLayout()
        appearance_form.addRow("Font size:", self.font_size_spin)
        appearance_form.addRow("Theme:", self.theme_combo)
        appearance_group = QGroupBox("Appearance")
        appearance_group.setLayout(appearance_form)

        # ===== Data & backups =============================================
        # Folder field: an editable path plus a "Browse…" button. The user can
        # type a path directly or pick one with the native folder dialog.
        self.data_dir_edit = QLineEdit(str(storage.default_data_dir()))
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse)
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.addWidget(self.data_dir_edit)
        folder_row.addWidget(browse_button)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)

        self.autosave_check = QCheckBox("Enable autosave")
        self.autosave_check.setChecked(settings.is_autosave_enabled())

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(
            settings.MIN_AUTOSAVE_INTERVAL, settings.MAX_AUTOSAVE_INTERVAL
        )
        self.interval_spin.setSuffix(" min")
        self.interval_spin.setValue(settings.get_autosave_interval_minutes())

        self.backup_spin = QSpinBox()
        self.backup_spin.setRange(settings.MIN_BACKUP_COUNT, settings.MAX_BACKUP_COUNT)
        self.backup_spin.setValue(settings.get_backup_count())

        data_form = QFormLayout()
        data_form.addRow("Data folder:", folder_widget)
        data_form.addRow("", self.autosave_check)
        data_form.addRow("Autosave every:", self.interval_spin)
        data_form.addRow("Backups to keep:", self.backup_spin)
        data_group = QGroupBox("Data & backups")
        data_group.setLayout(data_form)

        # ===== OK / Cancel ================================================
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(appearance_group)
        layout.addWidget(data_group)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        """Open the native folder picker and put the result in the path field."""
        start = self.data_dir_edit.text().strip() or str(storage.default_data_dir())
        folder = QFileDialog.getExistingDirectory(self, "Choose data folder", start)
        if folder:  # empty string means the user cancelled
            self.data_dir_edit.setText(folder)

    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        """Validate and save every setting, applying the live ones, then close."""
        # Apply the data-folder change first; if it fails validation, stay open
        # so the user can correct it without losing their other edits.
        if not self._apply_data_dir():
            return

        size = self.font_size_spin.value()
        settings.set_font_size(size)
        self._apply_font_size(size)

        chosen_theme = self.theme_combo.currentData()
        settings.set_theme(chosen_theme)
        theme.apply_theme(chosen_theme)

        settings.set_autosave_enabled(self.autosave_check.isChecked())
        settings.set_autosave_interval_minutes(self.interval_spin.value())
        settings.set_backup_count(self.backup_spin.value())

        self.accept()

    # ------------------------------------------------------------------
    def _apply_data_dir(self) -> bool:
        """Validate and apply any change to the data folder. Returns success.

        Handles the cases: no change; an unwritable target (warn and abort);
        a target that already holds Helena data (ask which copy to keep); and a
        fresh target (offer to bring the existing data along). Returns False only
        when the dialog should stay open (a validation problem).
        """
        chosen = self.data_dir_edit.text().strip()
        old_dir = storage.default_data_dir().resolve()

        # An empty field means "revert to the OS default location".
        if chosen:
            new_dir = Path(chosen).expanduser().resolve()
        else:
            new_dir = storage.system_default_data_dir().resolve()

        if new_dir == old_dir:
            return True  # Nothing changed.

        # Make sure we can actually create and write there before committing.
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
            probe = new_dir / ".helena_write_test"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError:
            QMessageBox.warning(
                self,
                "Invalid folder",
                f"Helena can't write to:\n{new_dir}\n\nPlease choose another folder.",
            )
            return False

        # Decide what to do with the data files at the new location.
        if (new_dir / storage.DATA_FILENAME).exists():
            # The destination already holds a Helena data file.
            keep_existing = QMessageBox.question(
                self,
                "Folder already has data",
                "The selected folder already contains Helena data.\n\n"
                "Keep the data that's already there?\n"
                "• Yes — use the existing file (your current data stays behind).\n"
                "• No — overwrite it with your current data.",
            )
            if keep_existing == QMessageBox.StandardButton.No:
                storage.move_data(old_dir, new_dir, overwrite=True)
            # If Yes: leave both folders untouched; we simply point at the new one.
        else:
            # Empty destination: offer to bring the existing data across.
            move = QMessageBox.question(
                self,
                "Move data?",
                "Move your existing data to the new location?",
            )
            if move == QMessageBox.StandardButton.Yes:
                storage.move_data(old_dir, new_dir)

        # Persist the override ("" when reverting to the OS default location).
        settings.set_data_dir("" if not chosen else str(new_dir))
        return True

    # ------------------------------------------------------------------
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
