# Helena

A cross-platform desktop productivity app built with Python and PySide6.

## About this project

Helena is a learning project. It was built with the help of AI using a
**problem-based learning** approach: each feature started as a concrete problem,
and the solution was reasoned through and explained along the way. The aim was
to learn how to design and build desktop user interfaces in Python with
**PySide6**.

The interface is written entirely **in code** — there are no Qt Designer
drag-and-drop `.ui` files. Every widget, layout, signal, and style is defined in
Python, which keeps the whole UI visible in plain diffs and makes the underlying
Qt concepts explicit.

## Features

**Lists**
- Organize tasks into multiple todo lists, shown as tabs
- Add a list with the **Add list** button at the right of the tab row, rename it
  by double-clicking its tab, or remove it with the tab's ✕
- Reorder lists by dragging tabs horizontally

**Tasks**
- Add a task (title + optional notes) from a dialog, tick it complete, or remove it
- Reorder tasks by dragging them vertically
- Each task has a **title** and free-text **notes**, edited in a detail panel
  beside the list — select a task to edit it, or double-click it to jump
  straight to its notes
- Tasks are shown as outlined cards for clearer visual separation

**Settings**
- **Theme**: System (follows the OS), Light, or Dark — applied live
- Adjustable UI font size
- Configurable autosave (on/off and interval) and number of backups to keep
- Configurable data-storage location
- Preferences are remembered between runs
- Open settings with the gear button at the bottom of a list, or press `Ctrl+,`

**Data**
- Autosaves while you work and on close; save immediately with `Ctrl+S`
- Timestamped backups (written on each manual save and on close) let you recover
  from a bad edit
- Atomic writes, so a crash can't corrupt the data file
- Stored as human-readable JSON in a configurable location; existing data can be
  moved when you change the location

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

Install dependencies into a managed virtual environment:

```bash
uv sync
