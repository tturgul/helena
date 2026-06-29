# Design Log

Last updated: 29.06.2026

### Project Summary

A cross-platform desktop productivity application built with Python and PySide6, focused on task management and personal organization.

### Architecture Decisions

- Desktop-first
- Local-first data storage
- JSON for persistence of todo data
- User preferences stored separately via Qt's QSettings (preferences vs. documents)
- UI organized by layer: pure data models, persistence/preferences modules, and PySide6 widgets under `ui/`

### Open Questions

- Is JSON sufficient for long-term storage, or should the application use a SQL database?
- Should the application support importing and exporting data in multiple formats (e.g., Markdown, JSON, CSV)?
- How should the application be packaged and distributed across platforms?
- Should icons adapt automatically to light/dark themes (recolour from the palette) rather than using a fixed colour?

## Entries

### 25.06.2026 — Initial Scope Definition

**Context**  
I have different feature ideas in mind and need to decide where to begin and how to proceed with the implementation.

**Decision**  
Adopt an iterative development approach and start by implementing a todo list.

**Why**  
Task management is a core capability of the envisioned application. Even as a standalone feature, a todo list provides immediate value and creates a solid foundation for future functionality. Keeping the initial scope small reduces complexity and increases the likelihood of shipping a usable first version.

**Next Steps**
- Define the task data model
- Define the todo-list data model
- Sketch the main window layout
- Implement task creation, editing, and deletion
- Implement task sorting and ordering
- Persist data to JSON
- Create a minimal usable prototype

### 29.06.2026 — Iteration 2: Todo UI Improvements

**Context**  
The first iteration shipped a working todo list. This iteration refines the UX around five goals: a more intuitive way to create lists, larger text, a settings surface, clearer visual separation between tasks, and richer tasks that carry notes in addition to a title.

**Decisions**
- **Create-list control**: replaced the old "+ New List" toolbar button with a plain **"Add list"** button pinned to the top-right of the tab row (a QTabWidget corner widget). Its right padding is measured at runtime to mirror the first tab's left inset, so it looks symmetric across Qt styles. (Rejected along the way: a literal "+" tab, and a custom green-styled button — the stylesheet broke native sizing and it didn't scale or align with the rest of the chrome.)
- **Text size**: the base UI font is set application-wide (default 12 pt) and is now a user preference rather than a constant.
- **Preferences storage**: QSettings (OS-native), kept separate from `todo_data.json`.
- **Settings UI**: a modal QDialog (QFormLayout) with font size as the first setting, applied live so the change is visible immediately.
- **Settings access**: after trying a tab-bar gear, a hamburger menu, a top menu bar, and a status-bar gear, settled on a small **gear button inside each list's input row** plus a `Ctrl+,` shortcut — minimal chrome, no extra bars. The list widget emits a custom `settings_requested` signal that the window handles, keeping the app-level concern out of the list widget. The gear is a bundled SVG icon whose height is pinned to the text buttons and whose size tracks the font.
- **Visual separation**: each task row gets a card-like outline via a QListWidget stylesheet using `palette()` roles, so it adapts to light/dark themes.
- **Task notes**: added a `body` field to the Task model (backward-compatible JSON). Each list became a QSplitter — the task list on the left, a title + notes detail editor on the right that follows the selection and writes back live. Inline rename was retired; double-click now focuses the notes editor.

**Why**  
The detail side-panel was chosen over inline expand/collapse cards because it adds notes with low risk — checkboxes and drag-reorder keep working untouched. It also provides a cleaner, less intrusive interaction that aligns well with the application's overall look and feel. QSettings keeps preferences cleanly separate from document data. The settings-access exploration converged on a button-light, focus-mode aesthetic after every persistent affordance I tried felt out of place.

**Note**  
A suspected `SyntaxError` in `storage.py`'s `except` clause turned out not to be a bug: Python 3.14 (PEP 758) makes the parentheses around multiple exception types optional, so `except OSError, json.JSONDecodeError:` is valid and ruff normalizes to that form. Relatedly, PEP 649 (3.14) makes annotations lazy by default, which is why the model's classmethods can return their own class without `from __future__ import annotations`.

**Next Steps**
- Allow users to switch between dark and light mode
- Add custom app icon(s)
- Implement periodic auto-saves / backups
- Allow users to set the data storage location
- Fix the cut off "Add a task and press Enter" text
- Consider unifying add list and add task behavior
