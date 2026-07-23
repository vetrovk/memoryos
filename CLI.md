# MemoryOS CLI

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
memory digest
memory doctor
memory rebuild
memory stats
memory graph
memory agents oracle --target AGENTS.md
```

## `memory init`

```bash
memory init
```

Initializes an empty memory home with the required folders and local SQLite index. It does not add example notes, user records, or demo search results. Running it again preserves existing Markdown notes and rebuilds the derived index without overwriting user data.

See [examples/example-decision.md](examples/example-decision.md) for a standalone note-format example. It is not installed into a memory home.

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

`--dry-run` does not save notes or move files. A successful import verifies the SQLite note, then moves the source to `.memoryos_pending/archive/`. Failed files remain in place and are recorded in `memory.log`; one bad JSON file does not stop the batch. The local SHA-256 state file prevents re-importing a copied or retried record.

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
