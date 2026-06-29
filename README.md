# Helena

A cross-platform desktop productivity app built with Python and PySide6.

## Features

**Lists**
- Organize tasks into multiple todo lists, shown as tabs
- Add a list with the **Add list** button at the right of the tab row, rename it
  by double-clicking its tab, or remove it with the tab's ✕
- Reorder lists by dragging tabs horizontally

**Tasks**
- Add tasks, mark them complete with a checkbox, and remove them
- Reorder tasks by dragging them vertically
- Each task has a **title** and free-text **notes**, edited in a detail panel
  beside the list — select a task to edit it, or double-click it to jump
  straight to its notes
- Tasks are shown as outlined cards for clearer visual separation

**Settings**
- Adjustable UI font size, remembered between runs
- Open settings with the gear button at the bottom of a list, or press `Ctrl+,`

**Data**
- Saved to JSON automatically on close and reloaded on start

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

Install dependencies into a managed virtual environment:

```bash
uv sync
```

## Run

```bash
uv run helena
```

## Documentation

- [Design log](docs/design-log.md) — why key decisions were made
