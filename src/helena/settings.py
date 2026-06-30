"""User-preferences storage, backed by Qt's QSettings.

QSettings persists small key/value preferences in the OS-native location
(the registry on Windows, a plist on macOS, an ini file on Linux). It is
deliberately separate from ``todo_data.json``: that file holds *documents*
(your lists and tasks), while this holds *preferences* (how the app looks and
behaves, and where the documents are stored). Different concerns, so we keep
them apart.

QSettings locates its storage using the application/organization names set in
``app.py``, so no path handling is needed here.

Every getter is defensive: QSettings can hand values back as strings (and
booleans as the strings "true"/"false") on some platforms, so we coerce and
fall back to a sensible default rather than trusting the stored type. Numeric
preferences are clamped to a valid range so a corrupt or hand-edited value can
never put the app into an unusable state.

QSettings returns values as a dynamically-typed object (the stubs type it as
``object``), so the integer getters annotate the raw value as ``Any`` before
coercing it — this reflects reality and keeps static type checkers happy.
"""

from typing import Any

from PySide6.QtCore import QSettings

# --- Keys --------------------------------------------------------------------
# Each key uses a "group/name" form. The part before the slash is a QSettings
# "group" — a namespace that keeps related keys tidy as the app grows.
FONT_SIZE_KEY = "ui/font_size"
THEME_KEY = "ui/theme"
DATA_DIR_KEY = "data/dir"
AUTOSAVE_ENABLED_KEY = "autosave/enabled"
AUTOSAVE_INTERVAL_KEY = "autosave/interval_minutes"
BACKUP_COUNT_KEY = "backups/keep"

# --- Font size ---------------------------------------------------------------
DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 24

# --- Theme -------------------------------------------------------------------
# The three values the theme setting may take. "system" means "follow the OS
# appearance"; the other two force a fixed appearance regardless of the OS.
THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
VALID_THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)
DEFAULT_THEME = THEME_SYSTEM

# --- Autosave / backups ------------------------------------------------------
DEFAULT_AUTOSAVE_ENABLED = True
DEFAULT_AUTOSAVE_INTERVAL = 2  # minutes
MIN_AUTOSAVE_INTERVAL = 1
MAX_AUTOSAVE_INTERVAL = 30
DEFAULT_BACKUP_COUNT = 5
MIN_BACKUP_COUNT = 0
MAX_BACKUP_COUNT = 20


def _coerce_bool(raw: object, default: bool) -> bool:
    """Interpret a QSettings value as a bool, tolerating string forms.

    QSettings may return a real ``bool`` or the strings ``"true"`` / ``"false"``
    depending on the platform and how the value was written, so we normalise
    both. Anything unrecognised falls back to ``default``.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() == "true"
    return default


# --- Font size ---------------------------------------------------------------
def get_font_size() -> int:
    """Return the saved UI font size in points, or the default if unset.

    The stored value is coerced to int and clamped to [MIN, MAX] so a missing,
    corrupt, or hand-edited value can't produce an unusable interface.
    """
    raw: Any = QSettings().value(FONT_SIZE_KEY, DEFAULT_FONT_SIZE)
    try:
        size = int(raw)
    # ``except A, B`` without parentheses is valid on Python 3.14+ (PEP 758).
    except TypeError, ValueError:
        return DEFAULT_FONT_SIZE
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))


def set_font_size(size: int) -> None:
    """Persist the UI font size (in points)."""
    QSettings().setValue(FONT_SIZE_KEY, int(size))


# --- Theme -------------------------------------------------------------------
def get_theme() -> str:
    """Return the saved theme: "system", "light", or "dark".

    Falls back to the default if the stored value is missing or not one of the
    recognised options.
    """
    raw = QSettings().value(THEME_KEY, DEFAULT_THEME)
    value = str(raw).strip().lower()
    return value if value in VALID_THEMES else DEFAULT_THEME


def set_theme(theme: str) -> None:
    """Persist the theme. Unknown values are coerced to the default."""
    QSettings().setValue(THEME_KEY, theme if theme in VALID_THEMES else DEFAULT_THEME)


# --- Data directory ----------------------------------------------------------
def get_data_dir() -> str:
    """Return the user's custom data directory, or "" when none is set.

    An empty string means "use the OS default location" — i.e. no override.
    ``storage`` interprets this when deciding where to read and write.
    """
    raw = QSettings().value(DATA_DIR_KEY, "")
    return str(raw) if raw else ""


def set_data_dir(path: str) -> None:
    """Persist the custom data directory; an empty string clears the override."""
    QSettings().setValue(DATA_DIR_KEY, path)


# --- Autosave / backups ------------------------------------------------------
def is_autosave_enabled() -> bool:
    """Return whether periodic autosave is turned on."""
    return _coerce_bool(
        QSettings().value(AUTOSAVE_ENABLED_KEY, DEFAULT_AUTOSAVE_ENABLED),
        DEFAULT_AUTOSAVE_ENABLED,
    )


def set_autosave_enabled(enabled: bool) -> None:
    """Persist whether periodic autosave is turned on."""
    QSettings().setValue(AUTOSAVE_ENABLED_KEY, bool(enabled))


def get_autosave_interval_minutes() -> int:
    """Return the autosave interval in minutes, clamped to a sane range."""
    raw: Any = QSettings().value(AUTOSAVE_INTERVAL_KEY, DEFAULT_AUTOSAVE_INTERVAL)
    try:
        minutes = int(raw)
    # ``except A, B`` without parentheses is valid on Python 3.14+ (PEP 758).
    except TypeError, ValueError:
        return DEFAULT_AUTOSAVE_INTERVAL
    return max(MIN_AUTOSAVE_INTERVAL, min(MAX_AUTOSAVE_INTERVAL, minutes))


def set_autosave_interval_minutes(minutes: int) -> None:
    """Persist the autosave interval (in minutes)."""
    QSettings().setValue(AUTOSAVE_INTERVAL_KEY, int(minutes))


def get_backup_count() -> int:
    """Return how many timestamped backups to keep, clamped to a sane range."""
    raw: Any = QSettings().value(BACKUP_COUNT_KEY, DEFAULT_BACKUP_COUNT)
    try:
        count = int(raw)
    # ``except A, B`` without parentheses is valid on Python 3.14+ (PEP 758).
    except TypeError, ValueError:
        return DEFAULT_BACKUP_COUNT
    return max(MIN_BACKUP_COUNT, min(MAX_BACKUP_COUNT, count))


def set_backup_count(count: int) -> None:
    """Persist how many timestamped backups to keep."""
    QSettings().setValue(BACKUP_COUNT_KEY, int(count))
