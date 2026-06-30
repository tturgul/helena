"""The application's main window: a tabbed container of todo lists.

PySide6 concepts used here:

* **QMainWindow**: a top-level window with built-in places for a tool bar, menu
  bar, and status bar, plus a *central widget*. We put a ``QTabWidget`` in the
  centre; transient confirmations use a floating label rather than the status
  bar, so there is no permanent bottom chrome.
* **QTabWidget**: shows one child widget per tab. Tabs are *movable* (drag to
  reorder) and *closable* (an ✕ to remove a list).
* **Corner widget**: a QTabWidget can host a widget in a corner of its tab bar.
  We put an "Add list" button in the top-right corner; its right margin is set
  at runtime to match the first tab's left inset (see _sync_corner_padding).
* **QAction + shortcuts**: ``Ctrl+,`` opens Settings and ``Ctrl+S`` saves, with
  no menu bar — the actions live directly on the window.
* **Toast overlay**: a small floating ``QLabel`` with a fading opacity effect
  briefly confirms actions (e.g. a manual save) and then disappears.
* **QTimer**: drives both the periodic autosave and the toast's fade-out delay.
* **closeEvent**: an event handler Qt calls when the window is closing; we
  override it to save (with a backup) before the window goes away.

Saving strategy: edits set a *dirty* flag (via each list's ``content_changed``
signal). A timer flushes the data when dirty; ``Ctrl+S`` and closing save
immediately and also write a rotating backup. Each tab page is a
``TodoListWidget`` that remembers its own ``list_id`` so ids round-trip through
save / load. New and renamed lists are named through ``AddListDialog``.
"""

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QKeySequence,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from helena import settings, storage
from helena.models import TodoList
from helena.ui.add_list_dialog import AddListDialog
from helena.ui.settings_dialog import SettingsDialog
from helena.ui.todo_list_widget import TodoListWidget


class MainWindow(QMainWindow):
    """Top-level window holding one tab per todo list."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Helena")
        self.resize(700, 500)

        # True when there are in-memory changes not yet written to disk. The
        # autosave timer only writes when this is set, avoiding pointless I/O.
        self._dirty = False

        # --- Central tab widget ------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # drag tabs to reorder
        self.tabs.setTabsClosable(True)  # show a close button per tab
        # Double-clicking a tab lets the user rename the list.
        self.tabs.tabBarDoubleClicked.connect(self._on_rename_list)
        self.tabs.tabCloseRequested.connect(self._on_close_list)
        # Reordering tabs changes the saved order, so it counts as a change.
        self.tabs.tabBar().tabMoved.connect(self._mark_dirty)
        self.setCentralWidget(self.tabs)

        # --- "Add list" button, top-right corner of the tab bar ----------
        # Plain, native styling so it scales with the UI font. We keep a handle
        # on its layout so we can adjust the right margin at runtime (see
        # _sync_corner_padding) to match the first tab's left inset.
        add_list_button = QPushButton("Add list")
        add_list_button.clicked.connect(self._on_new_list)

        corner = QWidget()
        self._corner_layout = QHBoxLayout(corner)
        self._corner_layout.setContentsMargins(0, 0, 0, 0)
        self._corner_layout.addWidget(add_list_button)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        # --- Window shortcuts (no visible chrome) ------------------------
        # The actions live on the window, so the shortcuts work without a menu.
        # Settings is also reachable via the gear button inside each list.
        settings_action = QAction("Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        # PreferencesRole lets macOS move this into its standard application
        # menu; on other platforms it's a harmless no-op.
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._on_open_settings)
        self.addAction(settings_action)

        # Ctrl+S (Cmd+S on macOS) saves immediately. StandardKey.Save maps to the
        # right combo per platform automatically.
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_manual_save)
        self.addAction(save_action)

        # --- Autosave timer ----------------------------------------------
        # Created here; started/stopped and re-intervalled from settings by
        # _configure_autosave (also re-run after the Settings dialog closes).
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)

        # --- Transient "toast" overlay -----------------------------------
        # A small floating label that briefly confirms an action and fades out.
        # It's a direct child of the window (no layout), so it floats above the
        # tabs rather than taking permanent space.
        self._toast = QLabel(self)
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setStyleSheet(
            "QLabel {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border-radius: 11px;"
            "  padding: 6px 16px;"
            "}"
        )
        self._toast.hide()

        # The fade-out animates a graphics opacity effect attached to the label.
        self._toast_opacity = QGraphicsOpacityEffect(self._toast)
        self._toast.setGraphicsEffect(self._toast_opacity)
        self._toast_fade = QPropertyAnimation(self._toast_opacity, b"opacity", self)
        self._toast_fade.setDuration(400)
        self._toast_fade.setStartValue(1.0)
        self._toast_fade.setEndValue(0.0)
        self._toast_fade.finished.connect(self._toast.hide)

        # After a short fully visible delay, start the fade-out.
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast_fade.start)

        # --- Load saved data on startup ----------------------------------
        self._load()
        self._configure_autosave()

    # ------------------------------------------------------------------
    # Layout tweaks
    # ------------------------------------------------------------------
    def showEvent(self, event: QShowEvent) -> None:
        """Once shown, the tab geometry is final — sync the corner padding."""
        super().showEvent(event)
        # Defer one event-loop tick so layout has settled before we measure.
        QTimer.singleShot(0, self._sync_corner_padding)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the toast anchored to the bottom-centre as the window resizes."""
        super().resizeEvent(event)
        if self._toast.isVisible():
            self._position_toast()

    def _sync_corner_padding(self) -> None:
        """Match the Add-list button's right gap to the first tab's left inset.

        The space before the first tab is decided by the active Qt style, not a
        number we control, so we measure it and mirror it as the corner widget's
        right margin. This keeps the look symmetric across styles/themes.
        """
        tab_bar = self.tabs.tabBar()
        if tab_bar.count() == 0:
            return  # No tabs yet — nothing to align to.
        left_inset = tab_bar.tabRect(0).left()
        self._corner_layout.setContentsMargins(0, 0, left_inset, 0)

    # ------------------------------------------------------------------
    # Toast overlay
    # ------------------------------------------------------------------
    def _show_toast(self, text: str) -> None:
        """Flash a brief, self-fading confirmation message over the window."""
        self._toast.setText(text)
        self._toast.adjustSize()
        self._position_toast()
        # Cancel any in-flight fade and show fully opaque again.
        self._toast_fade.stop()
        self._toast_opacity.setOpacity(1.0)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(1200)  # stay solid for 1.2s, then fade out

    def _position_toast(self) -> None:
        """Centre the toast horizontally near the bottom edge of the window."""
        x = (self.width() - self._toast.width()) // 2
        y = self.height() - self._toast.height() - 28
        self._toast.move(x, y)

    # ------------------------------------------------------------------
    # List (tab) management
    # ------------------------------------------------------------------
    def _add_list_tab(self, todo_list: TodoList) -> None:
        """Create a tab for a TodoList and make it the current one."""
        page = TodoListWidget()
        # Each list's gear button asks the window to open Settings.
        page.settings_requested.connect(self._on_open_settings)
        # Any edit inside the list marks the document dirty for autosave.
        page.content_changed.connect(self._mark_dirty)
        page.load_from(todo_list)  # also copies the list's id onto the page
        index = self.tabs.addTab(page, todo_list.name)
        self.tabs.setCurrentIndex(index)
        # A new tab can change the first tab's inset (e.g. from 0 tabs to 1).
        QTimer.singleShot(0, self._sync_corner_padding)

    def _on_new_list(self) -> None:
        """Prompt for a title and add an empty list."""
        dialog = AddListDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._add_list_tab(TodoList(name=dialog.title()))
            self._mark_dirty()

    def _on_rename_list(self, index: int) -> None:
        """Rename the list whose tab was double-clicked."""
        if index < 0:
            return  # Double-click landed outside any tab.
        dialog = AddListDialog(
            self,
            title_text=self.tabs.tabText(index),
            window_title="Rename List",
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.tabs.setTabText(index, dialog.title())
            self._mark_dirty()

    def _on_close_list(self, index: int) -> None:
        """Remove a list after confirming with the user."""
        name = self.tabs.tabText(index)
        reply = QMessageBox.question(
            self,
            "Remove List",
            f"Remove the list “{name}” and all of its tasks?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if widget is not None:  # widget(index) is typed QWidget | None
                widget.deleteLater()  # ask Qt to free the removed page
            self._mark_dirty()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _on_open_settings(self) -> None:
        """Open the modal Settings dialog and react to anything it changed.

        The dialog saves and live-applies font/theme itself. Afterwards we
        re-read the autosave configuration (the user may have changed it) and,
        if the data location moved, reload the lists from the new place.
        """
        old_path = storage.default_data_path()
        dialog = SettingsDialog(self)
        dialog.exec()
        self._configure_autosave()
        if storage.default_data_path() != old_path:
            self._reload_all()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _collect_lists(self) -> list[TodoList]:
        """Build the model from the current tabs, in their visual order."""
        lists: list[TodoList] = []
        for index in range(self.tabs.count()):
            page = self.tabs.widget(index)
            assert isinstance(
                page, TodoListWidget
            )  # every tab page is a TodoListWidget
            name = self.tabs.tabText(index)
            lists.append(page.to_model(name=name))
        return lists

    def _load(self) -> None:
        """Load saved lists at startup and build a tab for each.

        Populating rows flags the document dirty as a side effect; the freshly
        loaded state matches disk, so we clear the flag afterwards.
        """
        for todo_list in storage.load():
            self._add_list_tab(todo_list)
        self._dirty = False

    def _reload_all(self) -> None:
        """Discard the current tabs and reload lists from disk.

        Used after the data location changes, so the window reflects whatever
        lives at the new location.
        """
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()
        self._load()

    def _mark_dirty(self, *args) -> None:
        """Flag that there are unsaved changes for the next autosave to flush.

        Accepts and ignores any extra arguments so it can be connected directly
        to signals that carry payloads (e.g. tabMoved).
        """
        self._dirty = True

    def _save(self, *, make_backup: bool = False) -> None:
        """Persist the current state and clear the unsaved-changes flag."""
        storage.save(self._collect_lists(), make_backup=make_backup)
        self._dirty = False

    def _on_autosave_tick(self) -> None:
        """Timer slot: save only if something changed since the last save."""
        if self._dirty:
            self._save()  # routine autosave: atomic write, no backup

    def _on_manual_save(self) -> None:
        """Ctrl+S: save now (with a backup) and flash a brief confirmation."""
        self._save(make_backup=True)
        self._show_toast("Saved")

    def _configure_autosave(self) -> None:
        """Start/stop and re-interval the autosave timer from current settings."""
        if settings.is_autosave_enabled():
            interval_ms = settings.get_autosave_interval_minutes() * 60 * 1000
            self._autosave_timer.setInterval(interval_ms)
            self._autosave_timer.start()
        else:
            self._autosave_timer.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Save (with a backup) when the window closes, then close normally."""
        self._save(make_backup=True)
        super().closeEvent(event)
