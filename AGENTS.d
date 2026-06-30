# Agent Rules

## Memory

Store durable memories only in:

memory/YYYY-MM-DD.md

Rules:

* Append only
* Never overwrite
* Never create timestamped memory files
* Never edit:

 * AGENTS.md
 * TOOLS.md
 * SOUL.md
 * MEMORY.md
* If nothing important exists, reply:
 NO_REPLY

Store only:

* Long-term preferences
* Durable project context
* Stable workflow state

Do not store:

* Logs
* Errors
* Temporary output
* Duplicate information
