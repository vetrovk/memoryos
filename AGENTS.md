# AGENTS.md

## Language

Вопросы, которые возникают в процессе работы, задавай по-русски.

## Project

This repository contains MemoryOS, a local first Markdown and SQLite memory system.

## Commands

```bash
python3 -m memoryos.cli init
python3 -m memoryos.cli rebuild
python3 -m memoryos.cli doctor
python3 -m memoryos.cli search "query"
python3 -m memoryos.cli learn --project <project> --goal "<goal>"
python3 -m memoryos.cli learn --from-session --actor codex --source codex
python3 -m memoryos.cli import-pending --dry-run
```

## Rules

- Do not send personal, health, or work memory data to external APIs.
- Do not enable launchd automation without explicit confirmation.
- Keep Markdown files human readable.
- Preserve frontmatter UUIDs.
- Prefer simple standard-library Python unless a dependency is clearly justified.
- Do not enable the pending-import launchd plist without explicit confirmation.

## MemoryOS workflow

After every successfully completed task, after checks and before the final response to the user, the agent must update MemoryOS with:

```bash
python3 -m memoryos.cli learn --from-session --actor codex --source codex
```

If the local launcher is available, this is also acceptable:

```bash
./memory learn --from-session --actor codex --source codex
```

In the final response, briefly state that MemoryOS was updated. If the learn command fails, report the error honestly in the final response instead of hiding it.

If MemoryOS reports `saved as draft` or `skipped`, mention that honestly when it matters. This is expected Memory Curator behavior, not a hidden failure.

Generated files are activity noise, not engineering memory. Do not try to force dependency, build, cache, or generated snapshots into permanent memory before the final workflow.
