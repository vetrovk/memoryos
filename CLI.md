# MemoryOS CLI

Primary command:

```bash
memory <command>
```

It is available after local editable install:

```bash
python3 -m pip install -e .
```

During local development you can also use:

```bash
python3 -m memoryos.cli <command>
```

or:

```bash
./memory <command>
```

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
memory digest
memory doctor
memory rebuild
memory stats
memory graph
memory agents oracle --target AGENTS.md
```

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
  --command-used "python3 -m memoryos.cli doctor" \
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

## `memory import-pending`

Imports local Codex Work files matching `.memoryos_pending/*.json` recursively. Default roots come from `~/Memory/_system/config/pending_import.json` and default to `~/Documents`.

```bash
memory import-pending
memory import-pending --dry-run
memory import-pending --days 7
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
