# MemoryOS Roadmap

## MVP

- Markdown objects with UUID frontmatter.
- SQLite schema with entity, link, tag, history, command, and FTS tables.
- Python API.
- CLI command surface.
- Filesystem import for Markdown and common project files.
- Context export for AI agents.
- Doctor, digest, stats, graph.
- Launchd template without automatic activation.
- Automatic task learning through `memory learn` and `memory learn --from-session`.
- Memory Curator with quality score, outcome, drafts, duplicate/noise filtering.
- Generated/dependency filtering, deterministic near-duplicate detection, and curator audit stats.
- GitHub PR memory through optional `gh` CLI.

## Next

- Preserve content hashes and history diffs.
- Add richer command extraction from fenced code blocks.
- Add Git metadata import.
- Generate project-specific AGENTS.md from richer templates.
- Add Obsidian-compatible backlinks.
- Add vector search behind `SearchProvider`.
- Add local web UI.
- Add homelab sync with explicit allowlist.
- Add optional adapters so Codex, ChatGPT, Claude Code, and other agents can call task learning with their native session metadata.
- Improve PR review extraction and map review comments to changed files.
