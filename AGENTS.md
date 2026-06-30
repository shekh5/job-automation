# Agent Workspace Rules

## Memory Rules

Store durable memories only in:

memory/YYYY-MM-DD.md

Rules:

* Create memory/ if it does not exist
* Append only, never overwrite
* Never create timestamped files
* Use canonical filenames only:
  memory/2026-06-01.md
* Never edit:

  * MEMORY.md
  * DREAMS.md
  * SOUL.md
  * TOOLS.md
  * AGENTS.md
* If nothing important exists to store, reply:
  NO_REPLY

Only store:

* Long-term user preferences
* Durable project context
* Stable workflow information

Do not store:

* Temporary debug output
* Conversation filler
* Duplicate information

## Context Hygiene

* Do not open `graphify-out/` unless the task explicitly asks for graph analysis or graphify output.
* Do not auto-load large docs, reports, manifests, or generated artifacts.
* Prefer targeted file reads over opening entire folders.
* Keep workspace context minimal unless the current task needs more.
