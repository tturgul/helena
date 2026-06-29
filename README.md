# Helena

A cross-platform desktop productivity app built with Python and PySide6.

## Features

- Multiple todo lists, shown as tabs
- Create, rename, and remove lists
- Reorder lists by dragging tabs horizontally
- Add, edit (double-click), complete (checkbox), and remove tasks
- Reorder tasks by dragging them vertically
- Data is saved to JSON automatically on close and reloaded on start

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
