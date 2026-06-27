"""A single todo list, shown as the contents of one tab.

This is your first real PySide6 *widget*, so it introduces several core ideas:

* **Composite widgets**: we subclass ``QWidget`` and arrange child widgets
  inside it with a *layout*. Layouts position and resize children for you — you
  almost never set pixel coordinates by hand in Qt.
* **Signals & slots**: Qt's event mechanism. A widget *emits a signal* when
  something happens (e.g. a button's ``clicked``); we *connect* that signal to a
  *slot* (a method) that reacts.
* **QListWidget**: a ready-made list control. We enable internal drag-and-drop
  so the user can reorder tasks vertically (goal 5) with no custom code.
* **Item flags & check states**: each row is a ``QListWidgetItem`` whose *flags*
  decide what the user can do to it (edit inline, check it, drag it). The check
  state is our done/undone checkbox.

Design note: this widget is the *live editing surface*; the dataclass model is
the *persistence format*. ``load_from`` converts model -> widget and ``to_model``
converts widget -> model. Reading ``to_model`` on save naturally captures the
current drag-reordered order.
"""

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from helena.models import Task, TodoList


class TodoListWidget(QWidget):
    """An editable view of one :class:`~helena.models.TodoList`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        # Always call the base-class __init__ first so Qt initializes the widget.
        super().__init__(parent)

        # The model id of the list this widget represents. The window overwrites
        # it when loading an existing list; a fresh widget gets its own id.
        self.list_id: str = str(uuid.uuid4())

        # --- The task list ------------------------------------------------
        self.list_widget = QListWidget()

        # InternalMove == let the user drag rows to reorder them *within* this
        # list. Qt handles the entire drag-and-drop interaction for us.
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        # Double-clicking an editable row starts inline text editing.
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)

        # --- The "add task" input row ------------------------------------
        self.input = QLineEdit()
        self.input.setPlaceholderText("Add a task and press Enter…")
        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")

        # Lay the input row out horizontally: [ line edit ][ Add ][ Remove ]
        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(self.add_button)
        input_row.addWidget(self.remove_button)

        # Stack the list on top of the input row, vertically.
        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addLayout(input_row)
        self.setLayout(layout)

        # --- Wire signals to slots ---------------------------------------
        # Clicking "Add" or pressing Enter in the line edit both add a task.
        self.add_button.clicked.connect(self._on_add_clicked)
        self.input.returnPressed.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)

    # ------------------------------------------------------------------
    # Slots: methods that react to user actions
    # ------------------------------------------------------------------
    def _on_add_clicked(self) -> None:
        """Create a new task from the text currently in the input box."""
        title = self.input.text().strip()
        if not title:
            return  # Ignore empty / whitespace-only input.
        self.add_task(Task(title=title))
        self.input.clear()  # Ready for the next entry.

    def _on_remove_clicked(self) -> None:
        """Remove the currently selected task, if any."""
        row = self.list_widget.currentRow()
        if row >= 0:
            # takeItem detaches the row; Python then garbage-collects it.
            self.list_widget.takeItem(row)

    # ------------------------------------------------------------------
    # Helpers: build rows and bridge widget <-> model
    # ------------------------------------------------------------------
    def add_task(self, task: Task) -> None:
        """Append a Task as a checkable, editable, draggable row."""
        item = QListWidgetItem(task.title)

        # Flags are combined with bitwise OR; each grants one capability.
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled  # row is active (not greyed out)
            | Qt.ItemFlag.ItemIsSelectable  # user can select it
            | Qt.ItemFlag.ItemIsEditable  # double-click to rename (goal 4)
            | Qt.ItemFlag.ItemIsDragEnabled  # draggable to reorder (goal 5)
            | Qt.ItemFlag.ItemIsUserCheckable  # shows a checkbox
        )
        # The check state *is* our "completed" flag.
        item.setCheckState(
            Qt.CheckState.Checked if task.completed else Qt.CheckState.Unchecked
        )
        # Stash the task's id on the row so we can preserve it on save. UserRole
        # is a "scratch" slot Qt reserves for application data on an item.
        item.setData(Qt.ItemDataRole.UserRole, task.id)

        self.list_widget.addItem(item)

    def load_from(self, todo_list: TodoList) -> None:
        """Populate this widget from a model object (used on startup)."""
        self.list_id = todo_list.id
        self.list_widget.clear()
        for task in todo_list.tasks:
            self.add_task(task)

    def to_model(self, name: str) -> TodoList:
        """Read the current widget state back into a model object.

        We walk the rows in their *current visual order*, so any drag-and-drop
        reordering the user did is captured here. The list ``name`` is owned by
        the tab/window, so it is passed in.
        """
        tasks: list[Task] = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            tasks.append(
                Task(
                    title=item.text(),
                    completed=item.checkState() == Qt.CheckState.Checked,
                    id=item.data(Qt.ItemDataRole.UserRole),
                )
            )
        return TodoList(name=name, tasks=tasks, id=self.list_id)
