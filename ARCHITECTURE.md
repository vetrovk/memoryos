# MemoryOS Architecture

MemoryOS is a local first personal memory layer for humans and AI agents.

It is not a notes app. Markdown files are the durable source material, SQLite is the fast local index, and the Python API is the stable surface used by CLI commands and future agents.

## Principles

- AI First
- Local First
- Markdown First
- SQLite First
- Human Readable
- Extensible
- Plugin Based
- Safe by Default

## Folder Layout

```text
~/Memory/
  00_inbox/
  10_projects/
  20_people/
  30_company/
  40_health/
  50_ai/
  60_guides/
  70_decisions/
  80_errors/
  90_archive/
  _system/
    database/
    config/
    logs/
    exports/
    plugins/
    scripts/
    cache/
```

## Object Model

Every object is a Markdown page with a permanent UUID in frontmatter. Filenames are human readable, but never treated as identity.

Minimum object types:

- `project`
- `person`
- `company`
- `guide`
- `decision`
- `error`
- `command`
- `session`
- `prompt`
- `idea`
- `health_note`
- `architecture`
- `repository`

## Frontmatter

```yaml
---
id: "uuid"
title: "Title"
type: "decision"
project: "oracle"
status: "active"
tags: ["architecture"]
created: "YYYY-MM-DD HH:MM"
updated: "YYYY-MM-DD HH:MM"
source: "manual"
parent: ""
related: []
aliases: []
---
```

## API First

The CLI calls `memoryos.api.Memory`. Future agents should use the API directly instead of shelling out when possible.

Core methods:

- `memory.add()`
- `memory.search()`
- `memory.context()`
- `memory.digest()`
- `memory.project()`
- `memory.person()`
- `memory.note()`
- `memory.command()`
- `memory.history()`
- `memory.import_repo()`
- `memory.export_context()`
- `memory.learn()`

## Automatic Task Learning

`memory.learn()` records a finished agent task as a structured `session` object. It captures project, goal, completed actions, changed files, errors, decisions, commands, findings, and recommendations.

The saved Markdown note is immediately upserted into SQLite. Changed files are stored as aliases and `changed_file` graph links. Commands are extracted into the `commands` table.

`memory.learn_from_session()` minimizes manual input by collecting local session evidence from the current working directory and git metadata. It supports dry-run previews and does not use external APIs or LLMs.

## Activity Log Vs Real Memory

MemoryOS separates raw activity from durable engineering memory:

```text
Session -> Draft -> Memory Curator -> Permanent Memory
```

The Memory Curator is deliberately simple and local. It calculates `quality_score`, sets `outcome`, skips duplicates and no-signal sessions, lowers score for temporary/runtime projects, and sends weak records to `_system/drafts/` instead of indexing them as permanent memory.

Permanent memory should keep decisions, errors, useful conclusions, PRs, review outcomes, merge/close/reject outcomes, and reusable engineering lessons.

## GitHub PR Memory

`memory github-pr <url>` and `memory learn --from-github-pr <url>` use the local GitHub CLI `gh` when available. They save `github_pr_learning` notes with PR metadata, review comments, outcome, changed files, linked issues, and lessons. No external API is called directly by MemoryOS; the optional integration is delegated to the user's local `gh` setup.

## Search

The MVP uses `SQLiteFTSSearchProvider`. The `SearchProvider` interface is intentionally separate so future engines can be added without changing the user-facing API:

- embeddings
- sqlite-vss
- Qdrant
- LanceDB
- Chroma

## Knowledge Graph

Links live in Markdown frontmatter (`parent`, `related`) and in SQLite (`links`). The MVP prints the graph as text through `memory graph`.
