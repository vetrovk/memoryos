# AGENTS.md

## Language

Вопросы, которые возникают в процессе работы, задавай по-русски.

## Project

This repository contains MemoryOS, a local first Markdown and SQLite memory system.

## Commands

After installing MemoryOS in an active virtual environment as described in the README, use the installed `memory` command:

```bash
memory init
memory rebuild
memory doctor
memory search "query"
memory learn --project <project> --goal "<goal>"
memory learn --from-session --actor codex --source codex
memory import-pending --dry-run
```

Do not fall back to the system Python or the repository-local `./memory` file. If `memory` is unavailable, install the project into the active virtual environment first.

## Required MemoryOS Lookup

Before substantive work that changes tracked files, project behavior, configuration, or leads to a Git commit, complete this lookup gate with the installed CLI:

```bash
memory context --cwd "$(git rev-parse --show-toplevel)" --session
memory search --cwd "$(git rev-parse --show-toplevel)" --query "<task terms>"
```

Before creating a commit, also run:

```bash
memory search --cwd "$(git rev-parse --show-toplevel)" --query "commit convention release"
```

Do not edit tracked files or create a commit until the lookup gate completes. It does not apply to simple read-only commands such as `pwd`, `git status`, or `memory --help`.

In commentary, report exactly one outcome: `MemoryOS lookup: found <note title or id>; applying <constraint>.`, `MemoryOS lookup: no relevant records for <terms>.`, or `MemoryOS lookup: unavailable: <reason>.`

## Rules

- Do not send personal, health, or work memory data to external APIs.
- Do not enable launchd automation without explicit confirmation.
- Keep Markdown files human readable.
- Preserve frontmatter UUIDs.
- Prefer simple standard-library Python unless a dependency is clearly justified.
- Do not enable the pending-import launchd plist without explicit confirmation.

## MemoryOS workflow

The repository owner authorizes a local-only summary of the current task to the configured MemoryOS home. It must not send data to a network destination or include credentials, secrets, or full private file contents.

After every successfully completed task, after checks and before the final response to the user, the agent must update MemoryOS with the installed CLI:

```bash
memory learn --from-session --actor codex --source codex
```

The command must come from the active virtual environment. Do not use the system Python or a repository-local launcher as a fallback.

In the final response, briefly state that MemoryOS was updated. If the learn command fails, report the error honestly in the final response instead of hiding it.

If MemoryOS reports `saved as draft` or `skipped`, mention that honestly when it matters. This is expected Memory Curator behavior, not a hidden failure.

If `memory learn --from-session` reports `saved pending session`, direct SQLite writing is unavailable in the current process. Treat the pending JSON path printed by the command as the durable result. Do not retry with the system Python or another launcher. Import it later from a writable environment with `memory import-pending --path <project-root>`.

Generated files are activity noise, not engineering memory. Do not try to force dependency, build, cache, or generated snapshots into permanent memory before the final workflow.
