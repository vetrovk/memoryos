# Changelog

All notable public changes to MemoryOS are documented here.

## [0.2.1] - 2026-07-23

### Fixed

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
