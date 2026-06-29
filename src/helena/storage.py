"""Persistence layer: load and save the todo data as JSON on disk.

This is the first module that touches Qt, but only for **path resolution** — it
has no visual component. ``QStandardPaths`` gives us the correct per-user,
per-OS data directory, which is the idiomatic Qt way to place application data.

The JSON file looks like:

    {
      "version": 1,
      "todo_lists": [ {TodoList...}, {TodoList...} ]
    }

We wrap the lists in a top-level object with a ``version`` field so we have room
to migrate the schema later without guessing what an old file means.
"""

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from helena.models import TodoList

# Bump this if the on-disk schema ever changes in a breaking way.
SCHEMA_VERSION = 1

# File name used inside the application-data directory.
DATA_FILENAME = "todo_data.json"


def default_data_path() -> Path:
    """Return the full path to the JSON data file, creating its folder.

    ``AppDataLocation`` resolves to the OS-appropriate per-user data dir. The
    exact location depends on ``QApplication.applicationName`` /
    ``organizationName`` being set — we do that in ``app.py``.
    """
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    folder = Path(base)
    # Ensure the directory exists so the very first save cannot fail.
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DATA_FILENAME


def load(path: Path | None = None) -> list[TodoList]:
    """Load and return the saved todo lists.

    Returns an empty list on first run (file missing) or if the file is empty /
    unreadable, so the app starts gracefully instead of crashing.
    """
    path = path or default_data_path()

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    # Two exception types listed *without* wrapping parentheses: that syntax is
    # valid on Python 3.14+ (PEP 758), which this project requires — it is NOT a
    # mistake, and ruff normalizes to this form. OSError covers read failures;
    # JSONDecodeError covers malformed JSON.
    except OSError, json.JSONDecodeError:
        # Corrupt or unreadable file: start fresh rather than crash. A later
        # iteration could back up the bad file and warn the user.
        return []

    return [TodoList.from_dict(item) for item in data.get("todo_lists", [])]


def save(todo_lists: list[TodoList], path: Path | None = None) -> None:
    """Write the given todo lists to disk as pretty-printed JSON.

    ``indent=2`` makes the file human-readable so you can inspect it while
    learning. ``ensure_ascii=False`` keeps non-English characters readable.
    """
    path = path or default_data_path()

    payload = {
        "version": SCHEMA_VERSION,
        "todo_lists": [todo_list.to_dict() for todo_list in todo_lists],
    }

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
