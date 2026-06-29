"""Data model for Helena's todo feature.

This module is the *pure data layer*. It deliberately contains **no PySide6 /
Qt imports** — only the standard library. Keeping the model framework-free means:

* It's trivial to unit-test (no GUI needed).
* The persistence format (JSON) is decoupled from the UI.
* If we ever swap the storage backend (JSON -> SQLite) or even the UI toolkit,
  this file barely changes.

The model is a small tree:

    TodoList
      └── Task  (many, ordered)

Order matters: a Task's index in ``TodoList.tasks`` *is* its sort order, and a
TodoList's index in the saved file *is* its tab order. We never store an
explicit "order" integer — list ordering already carries that information.

Note on annotations: the classmethods are annotated to return their own class
(e.g. ``-> Task``). On Python 3.14+ this needs no ``from __future__ import
annotations``, because annotations are evaluated lazily by default (PEP 649),
so the forward reference to the not-yet-fully-defined class is fine.
"""

import uuid
from dataclasses import dataclass, field


def new_id() -> str:
    """Return a fresh, unique identifier as a string.

    UUID4 gives every Task / TodoList a stable, unique id that survives saving
    and loading. Ids let us tell two items apart even if they share a title.
    """
    return str(uuid.uuid4())


@dataclass
class Task:
    """A single todo item.

    Attributes:
        title: The human-readable text of the task.
        completed: Whether the task is done (drives the checkbox in the UI).
        body: Optional free-text notes/description shown in the detail panel.
        id: Stable unique identifier (auto-generated if not supplied).
    """

    title: str
    completed: bool = False
    body: str = ""
    # ``default_factory`` calls ``new_id()`` for *each* new Task. (Using a plain
    # default would share one id across every instance — a classic bug.)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        """Convert this Task into plain, JSON-serializable types."""
        return {
            "id": self.id,
            "title": self.title,
            "completed": self.completed,
            "body": self.body,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Rebuild a Task from a dict previously produced by ``to_dict``.

        We use ``dict.get`` with defaults so partial / older save files still
        load instead of raising — cheap forward/backward compatibility. A file
        written before ``body`` existed simply loads with an empty body.
        """
        return cls(
            title=data.get("title", ""),
            completed=data.get("completed", False),
            body=data.get("body", ""),
            id=data.get("id", new_id()),
        )


@dataclass
class TodoList:
    """A named list of tasks — rendered as one tab in the UI.

    Attributes:
        name: The list's display name (shown as the tab label).
        tasks: Ordered tasks; index == sort order.
        id: Stable unique identifier.
    """

    name: str
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        """Serialize the list and all of its tasks, preserving task order."""
        return {
            "id": self.id,
            "name": self.name,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> TodoList:
        """Rebuild a TodoList (and its tasks) from a dict."""
        return cls(
            name=data.get("name", "Untitled"),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            id=data.get("id", new_id()),
        )
