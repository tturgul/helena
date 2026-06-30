"""Apply the user's light/dark/system theme to the running application.

How this works — and why it's done this way:

The UI is themed by installing an explicit ``QPalette`` on the application. Under
the cross-platform "Fusion" style (set in ``app.py``), every widget paints from
that palette, so one ``setPalette`` call recolours the whole app consistently on
every OS.

Two cooperating pieces are needed to make this reliable:

1. **Palette** — the actual colours every widget draws with.
2. **Colour-scheme hint** (``styleHints().setColorScheme``) — tells Qt and the
   platform which appearance we intend. This matters when we force an appearance
   that *contradicts* the OS: e.g. a light palette while the OS is in dark mode.
   Without the hint, the platform re-asserts its own (dark) palette over ours, so
   the forced light theme wouldn't stick. With it, our palette holds.

For the forced modes we set both. For "system" we set the hint to ``Unknown``
(follow the OS) and choose the palette from the OS scheme.

Detecting the OS scheme reliably is the subtle part. ``colorScheme()`` reports
the *effective* scheme, which becomes our override the moment we set one — and
reading it immediately after clearing an override returns a stale value. So we
capture the real OS scheme **once, on the first call, before any override is
ever set**, and then keep it current via the ``colorSchemeChanged`` signal (which
fires on genuine OS changes while we're following the system). "System" mode uses
that captured value, so switching to it takes effect immediately and also tracks
later OS changes.

One more subtlety — stylesheets: Qt resolves a stylesheet's ``palette(...)``
colours once at polish time and caches them, so a later palette change leaves
stylesheet-styled widgets (the task-list cards, the toast) showing old colours.
After changing the palette we re-polish every widget to force a re-resolve.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from helena import settings

# The theme the user last selected. The OS-scheme watcher consults it to decide
# whether an OS change should be acted on (only while following the system).
_current_theme = settings.DEFAULT_THEME

# The OS's colour scheme, captured before we ever set an override and then kept
# current by the colorSchemeChanged signal. Used to resolve "system" mode.
_os_scheme = Qt.ColorScheme.Unknown

# One-time setup guard (capture OS scheme + connect the watcher).
_initialized = False

# Reentrancy guard: setting the colour-scheme hint can emit colorSchemeChanged,
# whose handler may call back into _apply_current; this prevents a loop.
_applying = False


def apply_theme(theme: str) -> None:
    """Switch the application to the given theme name.

    ``theme`` is one of ``settings.VALID_THEMES``; anything unrecognised is
    treated as "follow the system". Safe to call at startup and again whenever
    the user changes the setting — the change is applied live.
    """
    global _current_theme

    app = QApplication.instance()
    if app is None:
        return

    _initialize_once()
    _current_theme = theme if theme in settings.VALID_THEMES else settings.THEME_SYSTEM
    _apply_current()


def _initialize_once() -> None:
    """Capture the OS colour scheme and start watching for OS changes.

    Runs on the first ``apply_theme`` call, which (at startup) happens before any
    override has been set — so ``colorScheme()`` here returns the true OS scheme.
    """
    global _initialized, _os_scheme
    if _initialized:
        return
    _os_scheme = QGuiApplication.styleHints().colorScheme()
    QGuiApplication.styleHints().colorSchemeChanged.connect(_on_os_scheme_changed)
    _initialized = True


def _apply_current() -> None:
    """Install the palette (and colour-scheme hint) for the current theme."""
    global _applying
    if _applying:
        return
    _applying = True
    try:
        app = QApplication.instance()
        if app is None:
            return
        hints = QGuiApplication.styleHints()

        if _current_theme == settings.THEME_DARK:
            hints.setColorScheme(Qt.ColorScheme.Dark)
            palette = _dark_palette()
        elif _current_theme == settings.THEME_LIGHT:
            hints.setColorScheme(Qt.ColorScheme.Light)
            palette = _light_palette()
        else:  # "system": follow the OS, using the scheme we captured/tracked.
            hints.setColorScheme(Qt.ColorScheme.Unknown)
            palette = (
                _dark_palette()
                if _os_scheme == Qt.ColorScheme.Dark
                else _light_palette()
            )

        app.setPalette(palette)
        _repolish_all_widgets(app)
    finally:
        _applying = False


def _on_os_scheme_changed(scheme: Qt.ColorScheme) -> None:
    """React to the user changing their OS appearance.

    Only acts while following the system: in fixed light/dark modes the user has
    chosen an appearance explicitly, and the signal there is just an echo of our
    own override (which we must ignore so it can't corrupt the cached OS scheme).
    """
    global _os_scheme
    if _current_theme != settings.THEME_SYSTEM:
        return
    _os_scheme = scheme
    _apply_current()


def _repolish_all_widgets(app: QApplication) -> None:
    """Re-run the style's polish on every widget so stylesheets refresh.

    A stylesheet resolves ``palette(...)`` references when the widget is first
    polished and then caches them, so a later palette change leaves those colours
    stale. Unpolishing and re-polishing each widget makes the style recompute the
    stylesheet against the current palette; ``update()`` schedules a repaint.
    Only runs on a theme change, so the cost is negligible.
    """
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


def _light_palette() -> QPalette:
    """Return Fusion's standard light palette.

    Rather than hand-pick light colours, we borrow the ones the Fusion style
    ships with — a clean, neutral light scheme that's guaranteed self-consistent.
    """
    fusion = QStyleFactory.create("Fusion")
    return fusion.standardPalette()


def _dark_palette() -> QPalette:
    """Return a hand-built dark palette covering every role we rely on.

    Each ``setColor`` assigns one *role* (Window background, Text, Button, the
    selection Highlight, etc.). Setting them all is what makes the dark theme
    complete instead of half-applied. The ``Disabled`` group is given dimmer
    colours so greyed-out controls still read as disabled.
    """
    palette = QPalette()

    # Core surface and text colours.
    window = QColor(53, 53, 53)  # general window/background grey
    base = QColor(35, 35, 35)  # text-entry / list backgrounds (darker)
    alternate = QColor(45, 45, 45)  # alternating-row background
    text = QColor(220, 220, 220)  # primary foreground text
    bright_text = QColor(255, 80, 80)  # for "danger" emphasis Qt may use
    highlight = QColor(42, 130, 218)  # selection / accent blue
    highlight_text = QColor(15, 15, 15)
    disabled = QColor(120, 120, 120)  # dimmed text for disabled controls

    # Backgrounds and general text.
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alternate)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled)

    # Buttons.
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, bright_text)

    # Tooltips.
    palette.setColor(QPalette.ColorRole.ToolTipBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)

    # Links and selection.
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, highlight_text)

    # Dimmed colours for the Disabled state, so inactive controls look inactive.
    disabled_group = QPalette.ColorGroup.Disabled
    palette.setColor(disabled_group, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Text, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.HighlightedText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Highlight, QColor(80, 80, 80))

    return palette
