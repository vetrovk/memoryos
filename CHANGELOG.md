# Changelog

All notable public changes to MemoryOS are documented here.

## [0.5.0] - 2026-07-28

### Added

- Optional stdio-only read-only MCP server with bounded search, project context, note opening, and memory statistics tools.

## [0.4.0] - 2026-07-28

### Added

- Local-only monthly JSONL usage events for lookup, note opening, deliberate note use, and session-learning outcomes.
- `memory stats` filters local usage by day or project and supports JSON output and confirmed reset.
- `memory open <note-id>` and `memory used <note-id>` distinguish opened records from records that actually influenced work.

## [0.3.0] - 2026-07-28

### Added

- `memory context --cwd <git-root>` and `memory search --cwd <git-root>` derive the project from the real Git checkout for reusable agent workflows.
- `memory agents audit` reports the state of project-level MemoryOS instructions without writing files.
- `memory agents sync --dry-run` and `--apply` safely update only marker-managed blocks or exact legacy generated templates.

### Changed

- Codex integration guidance now uses a one-time global `~/.codex/AGENTS.md` workflow instead of requiring a generated file in every Git project.

## [0.2.3] - 2026-07-27

### Fixed

- Read-only duplicate lookup errors no longer prevent session learning from reaching the pending fallback.
- In a sandbox or readonly memory home, `memory learn --from-session` now creates `.memoryos_pending/*.json` and exits successfully when that fallback is saved.

## [0.2.2] - 2026-07-27

### Fixed

- Session learning now preserves a Codex Work pending record when a sandbox or read-only memory home blocks direct writes.
- Pending fallback reports its saved path instead of exposing a SQLite traceback, and successful fallback exits with status `0`.
- Pending import accepts confirmed legacy Codex Work v1 payload envelopes and keeps SHA-256 markers to prevent re-importing identical records.
- Long Unicode session titles no longer cause invalid generated note or pending filenames.
- `memory doctor` now reports resolved storage paths and explains unavailable direct writes.

## [0.2.1] - 2026-07-23

### Added

- GitHub Private Vulnerability Reporting through the repository Security Advisories flow.

### Changed

- Clarified that the current filesystem import extension is an internal boundary, not a dynamic plugin system.

### Fixed

- `memory --version` now reports the installed package version.
- Fresh memory homes now initialize without seeded example notes or root-level demo documents.
- Completed session records no longer default to an active lifecycle status.
- Rebuild now reports partial indexing failures and exits non-zero when the derived index is incomplete.
- Pending import documentation now explains the default recursive scan scope and explicit `--path` use.
- Public privacy documentation is consistently available in English.

## [0.2.0] - 2026-07-23

### Added

- Bounded, read-only session context for coding-agent handoff with `memory context <project> --session`.
- Post-save verification for permanent session learning, covering Markdown persistence, metadata, SQLite indexing, and normal search retrieval.
- Focused test coverage for session context limits, stable ordering, verification failures, drafts, and CLI exit behavior.

### Changed

- Clarified public beta installation, launcher, pending fallback, and local-data guidance.
- Extended installed-CLI smoke coverage in CI for session context, pending dry-run, and doctor checks.

### Fixed

- Removed the unused legacy database shim from the runtime configuration.

## [0.1.0] - 2026-07-18

### Added

- Local Markdown notes with SQLite FTS5 search, links, aliases, command extraction, and history.
- Curated session learning with drafts, quality scores, generated-file filtering, and duplicate detection.
- GitHub PR memories with stable identities, lifecycle updates, and explicit legacy duplicate review.
- Structured OSS candidate memories with stable identities and verdict safeguards.
- Local pending-record import for `.memoryos_pending/*.json` workflows.
