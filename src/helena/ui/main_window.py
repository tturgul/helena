"""The application's main window: a tabbed container of todo lists.

New PySide6 concepts here:

* **QMainWindow**: a top-level window with built-in places for a tool bar, menu
  bar, status bar, and a *central widget*. We put a ``QTabWidget`` in the centre.
* **QTabWidget**: shows one child widget per tab. We make tabs *movable* (drag to
  reorder horizontally — goal 3) and *closable* (an ✕ to remove a list — goal 2).
* **closeEvent**: an event handler Qt calls when the window is closing. We
  override it to auto-save (goal 7). Overriding event handlers is the standard
  way to hook into a widget's lifecycle.

Each tab page is a ``TodoListWidget`` that remembers its own ``list_id``, so we
can round-trip ids through save / load.
"""

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolBar,
)

from helena import storage
from helena.models import TodoList
from helena.ui.todo_list_widget import TodoListWidget


class MainWindow(QMainWindow):
    """Top-level window holding one tab per todo list."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Helena — Todo")
        self.resize(600, 500)

        # --- Central tab widget ------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # drag tabs to reorder (goal 3)
        self.tabs.setTabsClosable(True)  # show a close button per tab (goal 2)
        # Double-clicking a tab lets the user rename the list.
        self.tabs.tabBarDoubleClicked.connect(self._on_rename_list)
        self.tabs.tabCloseRequested.connect(self._on_close_list)
        self.setCentralWidget(self.tabs)

        # --- A small toolbar with a "New List" button --------------------
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        new_list_button = QPushButton("+ New List")
        new_list_button.clicked.connect(self._on_new_list)
        toolbar.addWidget(new_list_button)

        # --- Load saved data on startup (goal 8) -------------------------
        self._load()

    # ------------------------------------------------------------------
    # List (tab) management
    # ------------------------------------------------------------------
    def _add_list_tab(self, todo_list: TodoList) -> None:
        """Create a tab for a TodoList and make it the current one."""
        page = TodoListWidget()
        page.load_from(todo_list)  # also copies the list's id onto the page
        index = self.tabs.addTab(page, todo_list.name)
        self.tabs.setCurrentIndex(index)

    def _on_new_list(self) -> None:
        """Prompt for a name and add an empty list."""
        name, ok = QInputDialog.getText(self, "New List", "List name:")
        if ok and name.strip():
            self._add_list_tab(TodoList(name=name.strip()))

    def _on_rename_list(self, index: int) -> None:
        """Rename the list whose tab was double-clicked (goal 2)."""
        if index < 0:
            return  # Double-click landed outside any tab.
        current = self.tabs.tabText(index)
        name, ok = QInputDialog.getText(self, "Rename List", "List name:", text=current)
        if ok and name.strip():
            self.tabs.setTabText(index, name.strip())

    def _on_close_list(self, index: int) -> None:
        """Remove a list after confirming with the user (goal 2)."""
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
        """Load saved lists at startup and build a tab for each (goal 8)."""
        for todo_list in storage.load():
            self._add_list_tab(todo_list)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Auto-save when the window closes (goal 7).

        Qt calls ``closeEvent`` as the window is about to close. We save the
        current state, then call the base implementation to let the close
        proceed normally.
        """
        storage.save(self._collect_lists())
        super().closeEvent(event)
