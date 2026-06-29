"""User-preferences storage, backed by Qt's QSettings.

QSettings persists small key/value preferences in the OS-native location
(the registry on Windows, a plist on macOS, an ini file on Linux). It is
deliberately separate from ``todo_data.json``: that file holds *documents*
(your lists and tasks), while this holds *preferences* (how the app looks and
behaves). Different concerns, so we keep them apart.

QSettings locates its storage using the application/organization names set in
``app.py``, so no path handling is needed here.
"""

from PySide6.QtCore import QSettings

# Key under which the UI font size (in points) is stored. The "ui/" prefix is a
# QSettings "group" — a namespace that keeps related keys tidy as we add more.
FONT_SIZE_KEY = "ui/font_size"

DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 24


def get_font_size() -> int:
    """Return the saved UI font size in points, or the default if unset.

    QSettings can hand values back as strings on some platforms, so we coerce
    defensively and fall back to the default if the stored value is missing or
    unparseable. We also clamp to [MIN, MAX] so a corrupt/hand-edited value
    can't produce an unusable interface.
    """
    raw = QSettings().value(FONT_SIZE_KEY, DEFAULT_FONT_SIZE)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_FONT_SIZE
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))


def set_font_size(size: int) -> None:
    """Persist the UI font size (in points)."""
    QSettings().setValue(FONT_SIZE_KEY, int(size))
