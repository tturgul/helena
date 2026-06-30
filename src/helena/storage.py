"""Persistence layer: load and save the todo data as JSON on disk.

This module owns *where* the data lives and *how* it is written safely. It
touches Qt only for path resolution (``QStandardPaths`` gives the correct
per-user, per-OS data directory); it has no visual component.

The JSON file looks like:

    {
      "version": 1,
      "todo_lists": [ {TodoList...}, {TodoList...} ]
    }

We wrap the lists in a top-level object with a ``version`` field so we have room
to migrate the schema later without guessing what an old file means.

Two robustness features live here:

* **Atomic writes** — we serialise to a temporary file and then atomically
  replace the real file with it, so a crash mid-save can never leave a
  half-written, corrupt file behind. You always end up with either the previous
  good file or the new good file, never something in between.
* **Rotating backups** — on request (manual save / app close) we copy the
  current file into a ``backups/`` sub-folder under a timestamped name and prune
  to the newest few, so an accidental bad edit can be recovered.

The data directory is configurable: if the user set a custom location it is
used, otherwise we fall back to the OS default (see ``default_data_dir``).
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from helena import settings
from helena.models import TodoList

# Bump this if the on-disk schema ever changes in a breaking way.
SCHEMA_VERSION = 1

# File name used inside the data directory.
DATA_FILENAME = "todo_data.json"

# Sub-folder (under the data directory) that holds timestamped backup copies.
BACKUP_DIRNAME = "backups"


def system_default_data_dir() -> Path:
    """Return the OS-appropriate per-user data directory, creating it.

    ``AppDataLocation`` resolves to the standard application-data location on
    each platform. The exact path depends on ``QApplication.applicationName`` /
    ``organizationName`` being set — we do that in ``app.py``.
    """
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    folder = Path(base)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def default_data_dir() -> Path:
    """Return the directory the data file should live in, creating it.

    If the user has chosen a custom location (stored in settings) we honour it;
    otherwise we use the OS default. Returning a freshly created directory means
    the very first save can never fail for lack of a folder.
    """
    override = settings.get_data_dir()
    if override:
        folder = Path(override).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    return system_default_data_dir()


def default_data_path() -> Path:
    """Return the full path to the JSON data file inside the data directory."""
    return default_data_dir() / DATA_FILENAME


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
    # valid on Python 3.14+ (PEP 758), which this project requires. OSError
    # covers read failures; JSONDecodeError covers malformed JSON.
    except OSError, json.JSONDecodeError:
        # Corrupt or unreadable file: start fresh rather than crash. The copies
        # in ``backups/`` are the recovery path if this ever happens.
        return []

    return [TodoList.from_dict(item) for item in data.get("todo_lists", [])]


def save(
    todo_lists: list[TodoList],
    path: Path | None = None,
    *,
    make_backup: bool = False,
) -> None:
    """Write the given todo lists to disk as pretty-printed JSON, atomically.

    ``indent=2`` makes the file human-readable so you can inspect it while
    learning. ``ensure_ascii=False`` keeps non-English characters readable.

    The write is atomic: we serialise to a temporary file in the *same*
    directory and then ``os.replace`` it over the destination. ``os.replace`` is
    atomic on every OS, so a crash can't corrupt the file.

    When ``make_backup`` is True, the existing file (the last known-good state)
    is copied into ``backups/`` before being overwritten, and old backups are
    pruned. We back up only at meaningful checkpoints (manual save / app close)
    rather than on every routine autosave, to avoid flooding the folder with
    near-identical copies.
    """
    path = path or default_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if make_backup:
        _rotate_backups(path, settings.get_backup_count())

    payload = {
        "version": SCHEMA_VERSION,
        "todo_lists": [todo_list.to_dict() for todo_list in todo_lists],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)

    # Write to a temp file in the same directory (so the final rename stays on
    # one filesystem and is therefore atomic), then swap it into place.
    tmp_path = path.parent / (path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _rotate_backups(path: Path, keep: int) -> None:
    """Copy the current data file into ``backups/`` and keep the newest few.

    Does nothing if there is no existing file yet (first run) or if ``keep`` is
    zero (backups disabled). Backup names embed a UTC timestamp so they sort
    chronologically and never collide.
    """
    if keep <= 0 or not path.exists():
        return

    backup_dir = path.parent / BACKUP_DIRNAME
    backup_dir.mkdir(parents=True, exist_ok=True)

    # e.g. "todo_data-20260630T142530Z.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"{path.stem}-{stamp}{path.suffix}"
    shutil.copy2(path, backup_dir / backup_name)

    # Prune: keep only the newest ``keep`` backups for this data file. The glob
    # sorts oldest-first by name (timestamps sort chronologically), so the
    # everything-but-the-last-``keep`` slice is the set to delete.
    backups = sorted(backup_dir.glob(f"{path.stem}-*{path.suffix}"))
    for stale in backups[:-keep]:
        stale.unlink(missing_ok=True)


def _remove_if_empty(directory: Path) -> None:
    """Delete ``directory`` only if it is completely empty.

    ``Path.rmdir`` removes an empty directory and raises ``OSError`` on a
    non-empty one, so this can never delete a folder that still holds files we
    don't own. That makes it safe to call on a data location the user might share
    with other files: if anything unrelated remains, the folder is left in place.
    Missing directories and permission errors are likewise ignored.
    """
    try:
        directory.rmdir()
    except OSError:
        pass  # not empty, doesn't exist, or not permitted — leave it untouched


def _prune_empty_data_dir(data_dir: Path) -> None:
    """Remove the emptied data directory and, for the OS default location, the
    organization folder above it — each only while empty.

    The OS default data location nests as ``<shared data root>/<Org>/<App>`` (on
    Linux, e.g. ``~/.local/share/Helena/Helena``). Removing only the ``<App>``
    folder would leave an empty ``<Org>`` folder behind, so when that ``<Org>``
    folder sits directly under the shared data root and is now empty, we remove
    it too.

    Safety: we never remove the shared data root itself, and for a *custom*
    location — whose parent is some folder of the user's, not the shared root —
    the parent is left untouched. Each removal is empty-only (see
    ``_remove_if_empty``), so nothing containing other files is ever deleted.
    """
    data_dir = data_dir.resolve()

    # Inner data dir: drop the emptied backups/ sub-folder first, then the dir.
    _remove_if_empty(data_dir / BACKUP_DIRNAME)
    _remove_if_empty(data_dir)

    # Organization folder: only prune it when it is the level directly beneath
    # the shared data root (i.e. the default-location nesting) — never otherwise.
    shared_root = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericDataLocation
        )
    ).resolve()
    org_dir = data_dir.parent
    if org_dir.parent == shared_root:
        _remove_if_empty(org_dir)


def move_data(old_dir: Path, new_dir: Path, *, overwrite: bool = False) -> None:
    """Move the data file (and its backups) from ``old_dir`` to ``new_dir``.

    Used when the user changes the data location and chooses to bring existing
    data along. The ``backups/`` sub-folder is moved too, so history is kept.

    ``overwrite`` controls what happens when the destination already holds a
    data file: when True the destination is replaced; when False an existing
    destination file is left untouched.

    After moving, the old location is tidied up so the app doesn't leave empty
    folders behind: the emptied data directory — and, for the OS default
    location, the organization folder nested above it — are removed, but only
    while empty (see ``_prune_empty_data_dir``).
    """
    new_dir.mkdir(parents=True, exist_ok=True)

    old_file = old_dir / DATA_FILENAME
    new_file = new_dir / DATA_FILENAME
    if old_file.exists():
        if new_file.exists():
            if not overwrite:
                return
            new_file.unlink()
        shutil.move(str(old_file), str(new_file))

    # Bring the backup history across as well, if any exists.
    old_backups = old_dir / BACKUP_DIRNAME
    if old_backups.is_dir():
        new_backups = new_dir / BACKUP_DIRNAME
        new_backups.mkdir(parents=True, exist_ok=True)
        for item in old_backups.iterdir():
            target = new_backups / item.name
            if target.exists():
                if not overwrite:
                    continue
                target.unlink()
            shutil.move(str(item), str(target))

    # Tidy up the old location (empty-only; see the helper for the boundaries).
    _prune_empty_data_dir(old_dir)
