"""A single todo list, shown as the contents of one tab.

Core PySide6 ideas used here:

* **Composite widgets & layouts**: we subclass ``QWidget`` and arrange children
  with layouts, which position and resize them for us.
* **QSplitter**: a draggable divider between two panes. The left pane is the task
  list plus a control row; the right pane is a detail editor for the selected
  task.
* **Signals & slots**: a widget emits a signal; we connect it to a method. We
  define our own signals too: ``settings_requested`` (asks the window to open
  Settings) and ``content_changed`` (tells the window the data is now dirty and
  due for an autosave), so this widget stays unaware of how either is handled.
* **QListWidget item data roles**: each row is a ``QListWidgetItem``. Beyond its
  visible text (the title) we stash extra data on it under *roles*: the task id
  at ``UserRole`` and the body text at ``UserRole + 1``.
* **Avoiding signal feedback loops**: populating the editors from a row would
  trigger their "changed" signals and write the value straight back. A small
  ``self._loading`` flag suppresses write-back while we load.
* **changeEvent / FontChange**: when the application font changes, Qt notifies
  each widget; we use that to keep the gear button sized to the current font.

Design note: this widget is the *live editing surface*; the dataclass model is
the *persistence format*. ``load_from`` converts model -> widget and ``to_model``
converts widget -> model, capturing the current drag-reordered order on save.
New tasks are created through a small modal dialog (``AddTaskDialog``); existing
tasks are edited inline in the right-hand detail panel.
"""

import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from helena.models import Task, TodoList
from helena.ui.add_task_dialog import AddTaskDialog

# Custom roles for data we attach to each row. UserRole is the first slot Qt
# reserves for application data; we use the next one for the body text.
ID_ROLE = int(Qt.ItemDataRole.UserRole)
BODY_ROLE = int(Qt.ItemDataRole.UserRole) + 1

# Bundled icon assets live in an "icons" folder next to this module.
_ICON_DIR = Path(__file__).parent / "icons"

# Gear icon size as a fraction of the gear button's height. The button height is
# pinned to the text buttons' height (see _sync_settings_button); the icon is
# sized a bit smaller so it sits comfortably inside without clipping.
_ICON_HEIGHT_RATIO = 0.55


class TodoListWidget(QWidget):
    """An editable view of one :class:`~helena.models.TodoList`."""

    # Emitted when the user clicks this list's gear button. The window connects
    # to it and opens the Settings dialog; this widget stays unaware of how.
    settings_requested = Signal()

    # Emitted whenever the list's contents change (task added/removed/reordered,
    # checkbox toggled, or title/notes edited). The window uses it to mark the
    # document dirty so the next autosave flushes it.
    content_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        # Always call the base-class __init__ first so Qt initializes the widget.
        super().__init__(parent)

        # The model id of the list this widget represents. The window overwrites
        # it when loading an existing list; a fresh widget gets its own id.
        self.list_id: str = str(uuid.uuid4())

        # Guard: True while we populate the detail editors from a row, so their
        # "changed" signals don't immediately write the value back.
        self._loading = False

        # --- The task list ------------------------------------------------
        self.list_widget = QListWidget()
        # InternalMove == let the user drag rows to reorder them within this
        # list. Qt handles the entire drag-and-drop interaction for us.
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        # Titles are edited in the detail panel, not inline, so we turn off the
        # list's built-in edit triggers.
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Give each row a card-like outline. ``palette(...)`` pulls colours from
        # the active theme, so it adapts to light and dark automatically.
        #
        # Selected rows intentionally keep the *normal* text colour
        # (``palette(text)``), not the usual "highlighted text" colour. The
        # checkbox tick is painted in the text colour, and the small check
        # indicator box keeps its normal (Base) background even when the row is
        # selected — so a highlighted-text-coloured tick would sit on a
        # same-toned box and become nearly invisible. Using the normal text
        # colour keeps the tick (and the label) legible in both light and dark.
        self.list_widget.setStyleSheet(
            """
            QListWidget::item {
                border: 1px solid palette(mid);
                border-radius: 6px;
                margin: 3px;
                padding: 6px;
            }
            QListWidget::item:selected {
                border: 1px solid palette(highlight);
                background-color: palette(highlight);
                color: palette(text);
            }
            """
        )

        # The list's underlying model emits one of these signals for every kind
        # of content change (insert/remove/move rows, or edit an item's data),
        # so funnelling them all into ``content_changed`` captures everything in
        # one place — including title/notes edits, which write back as item data.
        model = self.list_widget.model()
        model.rowsInserted.connect(self.content_changed)
        model.rowsRemoved.connect(self.content_changed)
        model.rowsMoved.connect(self.content_changed)
        model.dataChanged.connect(self.content_changed)

        # --- The control row (add / remove / settings) -------------------
        self.add_button = QPushButton("Add task")
        self.remove_button = QPushButton("Remove")

        # A gear button at the end of the row opens Settings. It's a QPushButton
        # with just an icon. An icon-only button is naturally shorter than a text
        # button, so we pin its height to the Add button's (see
        # _sync_settings_button) to keep the row aligned.
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(str(_ICON_DIR / "gear.svg")))
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(self.settings_requested)
        self._sync_settings_button()

        controls_row = QHBoxLayout()
        controls_row.addWidget(self.add_button)
        controls_row.addWidget(self.remove_button)
        controls_row.addStretch(1)  # push the gear to the right edge
        controls_row.addWidget(self.settings_button)

        # Left pane = list stacked on top of the control row.
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.list_widget)
        left_layout.addLayout(controls_row)

        # --- The detail editor (right pane) ------------------------------
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Task title")
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Add notes for this task…")

        self.detail_pane = QWidget()
        detail_layout = QVBoxLayout(self.detail_pane)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(QLabel("Title"))
        detail_layout.addWidget(self.title_edit)
        detail_layout.addWidget(QLabel("Notes"))
        detail_layout.addWidget(self.body_edit)
        # Disabled until a task is selected, so there's nothing to edit "into".
        self.detail_pane.setEnabled(False)

        # --- Splitter holds both panes side by side ----------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_pane)
        splitter.addWidget(self.detail_pane)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 300])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        # --- Wire signals to slots ---------------------------------------
        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        # Selecting a different row loads it into the detail editor.
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        # Double-click jumps straight to the notes editor for quick entry.
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        # Edits in the detail editor write back to the selected row live.
        self.title_edit.textEdited.connect(self._on_title_edited)
        self.body_edit.textChanged.connect(self._on_body_changed)

    # ------------------------------------------------------------------
    # Scaling: keep the gear button aligned with the text buttons
    # ------------------------------------------------------------------
    def changeEvent(self, event: QEvent) -> None:
        """Re-sync the gear button whenever the application font changes."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._sync_settings_button()

    def _sync_settings_button(self) -> None:
        """Align the gear button with the text buttons and size its icon.

        An icon-only QPushButton computes a shorter height than a text button,
        so they don't line up. We pin the gear button's height to the Add
        button's, then size the icon to a fraction of that height. Both follow
        the Add button's metrics, so everything scales together with the font.
        """
        button_height = self.add_button.sizeHint().height()
        self.settings_button.setFixedHeight(button_height)
        side = round(button_height * _ICON_HEIGHT_RATIO)
        self.settings_button.setIconSize(QSize(side, side))

    # ------------------------------------------------------------------
    # Slots: list / control actions
    # ------------------------------------------------------------------
    def _on_add_clicked(self) -> None:
        """Open the Add-task dialog and append the new task if confirmed."""
        dialog = AddTaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_task(Task(title=dialog.title(), body=dialog.body()))
            # Select the freshly added task so its detail panel opens.
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _on_remove_clicked(self) -> None:
        """Remove the currently selected task, if any."""
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)  # detaches the row; GC frees it
        # Refresh the detail panel for whatever is selected now (or nothing).
        self._load_detail(self.list_widget.currentItem())

    # ------------------------------------------------------------------
    # Slots: detail panel
    # ------------------------------------------------------------------
    def _on_current_item_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        """Load the newly selected task into the detail editor."""
        self._load_detail(current)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Double-click focuses the notes editor for quick note-taking."""
        self.body_edit.setFocus()

    def _load_detail(self, item: QListWidgetItem | None) -> None:
        """Populate the title/notes editors from a row (or clear them).

        We raise ``self._loading`` around the updates so the editors' "changed"
        signals don't fire write-back while we're loading.
        """
        self._loading = True
        if item is None:
            self.title_edit.clear()
            self.body_edit.clear()
            self.detail_pane.setEnabled(False)
        else:
            self.detail_pane.setEnabled(True)
            self.title_edit.setText(item.text())
            self.body_edit.setPlainText(item.data(BODY_ROLE) or "")
        self._loading = False

    def _on_title_edited(self, text: str) -> None:
        """Write the edited title back onto the selected row immediately."""
        item = self.list_widget.currentItem()
        if item is not None:
            item.setText(text)

    def _on_body_changed(self) -> None:
        """Write the edited notes back onto the selected row's body slot."""
        if self._loading:
            return  # Ignore changes we caused by loading the editor.
        item = self.list_widget.currentItem()
        if item is not None:
            item.setData(BODY_ROLE, self.body_edit.toPlainText())

    # ------------------------------------------------------------------
    # Helpers: build rows and bridge widget <-> model
    # ------------------------------------------------------------------
    def add_task(self, task: Task) -> None:
        """Append a Task as a checkable, draggable row carrying its body."""
        item = QListWidgetItem(task.title)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled  # row is active (not greyed out)
            | Qt.ItemFlag.ItemIsSelectable  # user can select it
            | Qt.ItemFlag.ItemIsDragEnabled  # draggable to reorder
            | Qt.ItemFlag.ItemIsUserCheckable  # shows a checkbox
        )
        item.setCheckState(
            Qt.CheckState.Checked if task.completed else Qt.CheckState.Unchecked
        )
        # Stash id + body on the row so both survive save/load and reordering.
        item.setData(ID_ROLE, task.id)
        item.setData(BODY_ROLE, task.body)
        self.list_widget.addItem(item)

    def load_from(self, todo_list: TodoList) -> None:
        """Populate this widget from a model object (used on startup)."""
        self.list_id = todo_list.id
        self.list_widget.clear()
        for task in todo_list.tasks:
            self.add_task(task)
        # Open the first task's detail by default, if there is one.
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def to_model(self, name: str) -> TodoList:
        """Read the current widget state back into a model object.

        We walk the rows in their current visual order, so any drag-and-drop
        reordering is captured here. The list ``name`` is owned by the
        tab/window, so it is passed in.
        """
        tasks: list[Task] = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            tasks.append(
                Task(
                    title=item.text(),
                    completed=item.checkState() == Qt.CheckState.Checked,
                    body=item.data(BODY_ROLE) or "",
                    id=item.data(ID_ROLE),
                )
            )
        return TodoList(name=name, tasks=tasks, id=self.list_id)
