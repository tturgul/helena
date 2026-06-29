"""The application's main window: a tabbed container of todo lists.

New PySide6 concepts here:

* **QMainWindow**: a top-level window with built-in places for a tool bar, menu
  bar, status bar, and a *central widget*. We put a ``QTabWidget`` in the centre.
* **No menu bar / no status bar**: settings is reached via a gear button inside
  each list's input row (which emits ``settings_requested``) and a Ctrl+,
  shortcut registered on the window — so there's no extra chrome.
* **QTabWidget**: shows one child widget per tab. We make tabs *movable* (drag to
  reorder horizontally) and *closable* (an ✕ to remove a list).
* **Corner widget**: a QTabWidget can host a widget in a corner of its tab bar.
  We put an "Add list" button in the top-right corner; its right margin is set
  at runtime to match the first tab's left inset (see _sync_corner_padding).
* **closeEvent**: an event handler Qt calls when the window is closing. We
  override it to auto-save.

Each tab page is a ``TodoListWidget`` that remembers its own ``list_id``, so we
can round-trip ids through save / load.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from helena import storage
from helena.models import TodoList
from helena.ui.settings_dialog import SettingsDialog
from helena.ui.todo_list_widget import TodoListWidget


class MainWindow(QMainWindow):
    """Top-level window holding one tab per todo list."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Helena — Todo")
        self.resize(700, 500)

        # --- Central tab widget ------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # drag tabs to reorder
        self.tabs.setTabsClosable(True)  # show a close button per tab
        # Double-clicking a tab lets the user rename the list.
        self.tabs.tabBarDoubleClicked.connect(self._on_rename_list)
        self.tabs.tabCloseRequested.connect(self._on_close_list)
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

        # --- Settings shortcut (no visible chrome) -----------------------
        # The action lives on the window, so Ctrl+, works without a menu. The
        # visible entry point is the gear button inside each list's input row.
        settings_action = QAction("Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        # PreferencesRole lets macOS move this into its standard application
        # menu; on other platforms it's a harmless no-op.
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._on_open_settings)
        self.addAction(settings_action)

        # --- Load saved data on startup ----------------------------------
        self._load()

    # ------------------------------------------------------------------
    # Layout tweaks
    # ------------------------------------------------------------------
    def showEvent(self, event: QShowEvent) -> None:
        """Once shown, the tab geometry is final — sync the corner padding."""
        super().showEvent(event)
        # Defer one event-loop tick so layout has settled before we measure.
        QTimer.singleShot(0, self._sync_corner_padding)

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
    # List (tab) management
    # ------------------------------------------------------------------
    def _add_list_tab(self, todo_list: TodoList) -> None:
        """Create a tab for a TodoList and make it the current one."""
        page = TodoListWidget()
        # Each list's gear button asks the window to open Settings.
        page.settings_requested.connect(self._on_open_settings)
        page.load_from(todo_list)  # also copies the list's id onto the page
        index = self.tabs.addTab(page, todo_list.name)
        self.tabs.setCurrentIndex(index)
        # A new tab can change the first tab's inset (e.g. from 0 tabs to 1).
        QTimer.singleShot(0, self._sync_corner_padding)

    def _on_new_list(self) -> None:
        """Prompt for a name and add an empty list."""
        name, ok = QInputDialog.getText(self, "New List", "List name:")
        if ok and name.strip():
            self._add_list_tab(TodoList(name=name.strip()))

    def _on_rename_list(self, index: int) -> None:
        """Rename the list whose tab was double-clicked."""
        if index < 0:
            return  # Double-click landed outside any tab.
        current = self.tabs.tabText(index)
        name, ok = QInputDialog.getText(self, "Rename List", "List name:", text=current)
        if ok and name.strip():
            self.tabs.setTabText(index, name.strip())

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

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _on_open_settings(self) -> None:
        """Open the modal Settings dialog (it saves & applies changes itself)."""
        dialog = SettingsDialog(self)
        dialog.exec()

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
        """Load saved lists at startup and build a tab for each."""
        for todo_list in storage.load():
            self._add_list_tab(todo_list)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Auto-save when the window closes.

        Qt calls ``closeEvent`` as the window is about to close. We save the
        current state, then call the base implementation to let the close
        proceed normally.
        """
        storage.save(self._collect_lists())
        super().closeEvent(event)
