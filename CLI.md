# MemoryOS CLI

This reference matches MemoryOS v0.5.1 Public Beta.

Primary command:

```bash
memory <command>
```

It is available after local editable install:

```bash
python -m pip install -e .
```

Use the installed command from the active virtual environment. The repository-local wrapper scripts remain for backward compatibility, but are not the documented fallback for agent workflows.

## Commands

```bash
memory init
memory add --title "Oracle Bot заметка" --type project --project oracle --tags "oracle,bot" --text "Описание."
memory import ~/Projects/OmniBot --project omnibot
memory import-pending --dry-run
memory learn --from-session --actor codex --source codex
memory drafts
memory github-pr https://github.com/owner/repo/pull/123
memory github-pr-deduplicate --dry-run
memory oss-candidate upsert --from-json candidate.json --actor codex --source oss-scout
memory learn --project oracle --goal "Fix search" --action "Updated SearchProvider" --file memoryos/search.py --command-used "memory doctor"
memory search "oracle bot"
memory search --project oracle --type decision
memory context oracle
memory context oracle --session
memory context --cwd "$(git rev-parse --show-toplevel)" --session
memory search --cwd "$(git rev-parse --show-toplevel)" --query "release notes"
memory digest
memory doctor
memory rebuild
memory stats
memory stats --days 7
memory stats --project oracle --json
memory open <note-id>
memory used <note-id> --project oracle --reason "Applied the deployment rule"
memory graph
memory agents audit --path ~/Documents --path ~/projects
memory agents sync --dry-run --path ~/Documents --path ~/projects
```

## `memory init`

```bash
memory init
```

Initializes an empty memory home with the required folders and local SQLite index. It does not add example notes, user records, or demo search results. Running it again preserves existing Markdown notes and rebuilds the derived index without overwriting user data.

See [examples/example-decision.md](examples/example-decision.md) for a standalone note-format example. It is not installed into a memory home.

## `memory stats`

```bash
memory stats
memory stats --days 7
memory stats --days 30 --project oracle
memory stats --json
memory stats --reset --yes
```

Shows local usage events from `_system/events/events-YYYY-MM.jsonl`: lookup status and duration, opened notes, deliberate note use, and session-learning outcomes. The JSONL files are local only and are not sent to a network destination. Set `MEMORYOS_TELEMETRY=0` to disable collection. Queries are normalized and obvious credentials, tokens, and long secret-like values are redacted; note bodies, prompts, and agent responses are never stored in these events.

`--reset` deletes only local event files and requires `--yes`. Statistics measure observed usage, not token savings or the quality of a resulting engineering decision.

## `memory open` and `memory used`

```bash
memory open <note-id>
memory used <note-id> --project oracle --reason "Applied the deployment rule"
```

`open` displays a note and records that it was opened. Use `used` only when the note actually influenced a decision, constraint, commit, or implementation. A search result that was merely viewed must not be marked as used.

## `memory agents`

```bash
memory agents audit --path ~/Documents --path ~/projects
memory agents sync --dry-run --path ~/Documents --path ~/projects
memory agents sync --apply --path ~/Documents --path ~/projects
```

`audit` recursively lists Git repositories and classifies each project-level `AGENTS.md` without writing: `missing`, current managed, stale managed, exact legacy generated, conflict, or unrelated. `sync --dry-run` reports only the updates that would be safe. `sync --apply` updates a marker-managed MemoryOS block, or migrates an exact legacy generated template after creating `AGENTS.md.memoryos.bak`. It never changes missing, unrelated, custom, ambiguous, or incomplete-marker files.

For global Codex integration, add the MemoryOS sections from the repository [AGENTS.md](AGENTS.md) to `~/.codex/AGENTS.md` once. The resulting instructions use `--cwd` to detect the actual Git checkout, so new projects do not need a generated file.

To create a new project-specific template intentionally:

```bash
memory agents my-project --target MEMORYOS-AGENTS.md
```

Generation refuses to overwrite an existing nonempty target. This is an instruction-file integration, not a native Codex integration.

## `memory mcp serve`

```bash
python -m pip install "memoryos-local[mcp]"
memory mcp serve
```

Runs an optional stdio-only MCP server. It exposes only `search_memory`, `get_project_context`, `open_memory`, and `get_memory_stats`. The server has no write tools, network transport, background daemon, or access to arbitrary local files. Results are bounded and omit memory-home paths. Without the optional dependency, the command prints the installation command and exits without affecting ordinary MemoryOS commands.

## Makefile Shortcuts

```bash
make init
make add TITLE="Заметка" TYPE=decision PROJECT=oracle TAGS="sqlite,архитектура" TEXT="Решение."
make import IMPORT_PATH=~/Projects/OmniBot PROJECT=omnibot
make import-pending
make learn-session PROJECT=oracle SOURCE=codex ACTOR=codex
make drafts
make github-pr PR_URL=https://github.com/owner/repo/pull/123
make learn PROJECT=oracle GOAL="Fix search" TAGS="codex,task-learning"
make learn-json LEARN_JSON=task-learning.json
make search QUERY="oracle bot"
make context PROJECT=oracle
make digest
make doctor
```

## `memory learn`

Saves a structured task-completion memory. The primary workflow is OpenAI Codex; other callers can use the same CLI or Python API without being a primary support target.

Automatic session capture:

```bash
memory learn --from-session --actor codex --source codex
memory learn --from-session --project memoryos --actor codex --source codex
memory learn --from-session --actor codex --source codex --dry-run
```

`--from-session` reads local git metadata only: current folder, git remote, `pyproject.toml`, `package.json`, README, `git status --short`, `git diff --stat`, changed files, and latest commit. It does not call external APIs and does not use an LLM.

`--from-session` is curated before permanent save. It calculates `quality_score`, sets `outcome`, skips duplicates/no-signal sessions, and may save weak records to `_system/drafts/`.

After a permanent `--from-session` save, MemoryOS verifies the Markdown file, required metadata, SQLite index, and retrieval through the normal FTS search path. A verification failure leaves the note untouched, exits non-zero, and suggests `memory doctor` or `memory rebuild` when the index is the failed check. Drafts are verified as files and metadata only; Curator skips remain successful skips.

If the current process cannot write the local SQLite index because of a readonly database or sandbox boundary, `--from-session` writes a recoverable Codex Work JSON record to `.memoryos_pending/` in the current project instead of showing a traceback. The command prints the exact path and an import command. A successful pending fallback exits with `0`, meaning the queue file was saved rather than that the main memory home was written. Keep the JSON until `memory import-pending --path <project-root>` reports success; if the fallback file cannot be written, the command exits non-zero.

### Bounded session context

```bash
memory context memoryos --session
memory context memoryos --session --limit 8 --max-bytes 4096
```

`--session` is opt-in and read-only. It does not write a note, export a file, start a background process, or call an LLM. The output uses existing indexed project memory, prioritizes active/unresolved records and relevant PR or OSS entities, then recent permanent notes. It is limited to the requested number of records and UTF-8 byte budget; the footer reports the actual size and whether output was truncated.

Generated files are activity noise, not engineering memory. The curator filters dependencies, build output, caches, temporary folders, Python bytecode, logs, `.DS_Store`, and common minified bundles before computing score, links, aliases, and session fingerprints. Customize defaults with `~/Memory/_system/config/curator.json`; see `examples/curator.json`.

Draft commands:

```bash
memory drafts
memory drafts review
memory drafts promote <id>
memory drafts drop <id>
memory curator-stats --days 7
memory cleanup-generated --dry-run
```

`memory curator-stats` reads the local curator audit from SQLite history. `memory cleanup-generated --dry-run` only reports old generated aliases/links; it never deletes data.

Manual capture:

```bash
memory learn \
  --project oracle \
  --goal "Fix search" \
  --action "Updated SQLite FTS query handling" \
  --file memoryos/search.py \
  --error "Ambiguous SQL column name" \
  --decision "Qualify notes.type in joined search queries" \
  --command-used "memory doctor" \
  --finding "Doctor is green" \
  --recommendation "Add regression test later" \
  --actor codex \
  --source codex
```

Agent JSON payload:

```bash
memory learn --from-json task-learning.json
```

`--from-json -` reads JSON from stdin.

### Credential guard

Commands that create permanent notes, drafts, pending learning, or structured upserts block high-confidence credentials before writing. Supported categories are private keys, GitHub tokens, OpenAI-style API keys, AWS access keys, and explicit values assigned to `password`, `api_key`, `access_token`, or `secret`. Errors contain the category but not the detected value. MemoryOS does not apply a general high-entropy heuristic.

For an intentional local save, add the explicit override to the writing command:

```bash
memory learn --project local --goal "Document a local fixture" --finding "api_key=local-fixture-value" --allow-credentials
memory import-pending --path "/path/to/projects" --allow-credentials
```

The same flag is available for `memory add`, `memory import`, `memory github-pr`, `memory learn --from-github-pr`, `memory oss-candidate upsert`, and `memory drafts promote`. Existing notes are not scanned or rewritten automatically.

## `memory rebuild`

Rebuild refreshes the derived SQLite index from eligible Markdown notes. It does not delete Markdown files or rewrite their frontmatter. The command prints `scanned`, `indexed`, `skipped`, and `failed` counts. It exits with `0` only when every eligible note was indexed; a partial index exits non-zero and lists each failed path with a short safe reason. Rebuild remains non-atomic in this beta: successfully indexed notes stay searchable, while failed notes remain in Markdown and should be inspected before retrying.

## `memory import-pending`

Imports local Codex Work files matching `.memoryos_pending/*.json` recursively. Default roots come from `~/Memory/_system/config/pending_import.json` and default to `~/Documents`. The scan reads only matching pending JSON files, not arbitrary documents under those roots. Use `--path` to avoid scanning all of `~/Documents`.

```bash
memory import-pending
memory import-pending --dry-run
memory import-pending --days 7
memory import-pending --dry-run --path "/path/to/projects"
memory import-pending --path "/path/to/projects"
```

`--dry-run` does not save notes or move files. A successful import verifies the SQLite note, then moves the source to `.memoryos_pending/archive/`. Files blocked by the credential guard remain in place and are reported as skipped without writing the detected value to logs or telemetry. Other failed files remain in place and are recorded in `memory.log`; one bad JSON file does not stop the batch. The local SHA-256 state file prevents re-importing a copied or retried record.

`memory doctor` performs a small SQLite write-and-rollback check. When direct writing is unavailable, it reports `DIRECT_WRITE_UNAVAILABLE` and points to the session pending fallback instead of treating the failure as an unexplained database problem.

For a daily macOS job, copy and fill the placeholders in `launchd/com.memoryos.import-pending.plist.example`; do not load it until you explicitly want scheduling enabled.

```bash
cp launchd/com.memoryos.import-pending.plist.example ~/Library/LaunchAgents/com.memoryos.import-pending.plist
# Replace __MEMORYOS_PYTHON__ with a stable venv Python where MemoryOS is installed,
# and replace __MEMORYOS_HOME__. Do not use the system Python or depend on the repository directory.
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.memoryos.import-pending.plist
launchctl bootout gui/$(id -u)/com.memoryos.import-pending
```

## GitHub PR Memory

```bash
memory learn --from-github-pr https://github.com/owner/repo/pull/123
memory github-pr https://github.com/owner/repo/pull/123
```

Requires GitHub CLI `gh` for the MVP. If `gh` is missing or cannot read the PR, MemoryOS reports the error and does not save a partial memory.

PR notes use `github-pr:<owner>/<repo>#<number>` as a stable identity. Repeated captures enrich one note and keep its UUID. Inspect old duplicate captures before archival migration:

```bash
memory github-pr-deduplicate --dry-run
memory github-pr-deduplicate --apply
```

`--apply` moves legacy duplicates to `90_archive/github_pr_duplicates/` after merging their capture text into the canonical note.

## `memory oss-candidate upsert`

```bash
memory oss-candidate upsert --from-json candidate.json
```

Required fields are `repository`, `issue_number`, `investigation_state`, and `verdict`. The stable key is `oss-candidate:<owner>/<repo>#<issue>`. Existing user or external PR flags force `SKIP`; an unchanged `INVESTIGATE FURTHER` report is skipped.
