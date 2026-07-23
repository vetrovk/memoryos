# MemoryOS Privacy

MemoryOS is a local-first public beta. Durable notes are Markdown files stored in the memory home selected by `MEMORY_HOME`, or `~/Memory` by default. SQLite, logs, caches, exports, drafts, and pending-import markers are local derived state under that home.

## Network Access

The core CLI and Python API do not make network requests or call hosted AI services. Optional workflows can invoke software configured separately on your machine. For example, GitHub PR capture calls the local `gh` CLI, and an external coding agent may have its own network permissions. Review those tools and permissions independently.

## Pending Records and Scan Scope

Pending records are JSON files in `.memoryos_pending/*.json`. They can contain task descriptions, outcomes, changed-file paths, findings, actor/source values, and a previous MemoryOS error. By default, `memory import-pending` recursively searches `~/Documents` for that exact directory and JSON pattern. It does not index or read arbitrary documents outside matching pending files.

Use `memory import-pending --path /path/to/projects` to restrict the search to a known project root. `--dry-run` reports matching candidates without importing, moving, or deleting them.

## Local Data Responsibilities

- Do not commit a real memory folder, SQLite database, logs, exports, drafts, pending records, or `.env` files to a public repository.
- Treat health, personal, and work notes as sensitive. Review filesystem permissions and backups before syncing a memory home or exporting context.
- Diagnostics and CLI output can contain note titles, file paths, project names, and error summaries. Avoid sharing them publicly without review.
- To remove MemoryOS data, archive or delete the local Markdown notes and derived state you no longer want, then run `memory rebuild` for the remaining notes. Back up important data first.

MemoryOS does not make guarantees about absolute privacy, security, or data loss. Verify your local permissions, backup process, and the behavior of any external agents or tools you connect to it.
