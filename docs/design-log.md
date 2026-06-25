# Design Log
Last updated: 25.06.2026

### Project Summary
A cross-platform desktop productivity application built with Python and PySide6, focused on task management and personal organization.

### Architecture Decisions
- Desktop-first
- Local-first data storage
- JSON for persistence

### Open Questions
- Is JSON sufficient for long-term storage, or should the application use a SQL database?
- Should the application support importing and exporting data in multiple formats (e.g., Markdown, JSON, CSV)?
- How should the application be packaged and distributed across platforms?

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

