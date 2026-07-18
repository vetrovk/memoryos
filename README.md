# MemoryOS

MemoryOS is a local Markdown and SQLite system for keeping engineering decisions, task outcomes, and investigation context searchable after a project session ends.

It helps when an engineer or agent has already investigated a failure, reviewed a pull request, or rejected an OSS candidate, but the next person has to repeat that work because the useful conclusion was lost in a terminal, chat, or commit history.

![MemoryOS flow](docs/images/memory-flow.svg)

## What It Does

- Captures structured task learning through a Python API or `memory learn`.
- Collects a local Git session with `memory learn --from-session`.
- Curates session records into permanent notes, drafts, or skips when the signal is weak or duplicated.
- Stores GitHub pull-request context and lifecycle updates in one durable note per PR.
- Stores one structured OSS candidate decision per repository issue.
- Imports local `.memoryos_pending/*.json` records from agent workflows.
- Keeps Markdown as the source of truth and SQLite FTS5 as the local search index.

No cloud service, external API, or LLM is required for the core workflow. GitHub PR capture optionally uses the locally configured `gh` CLI.

## How It Works

```text
Developer or agent
        |
      Session
        |
      Curator
   /    |     \
skip  draft  permanent Markdown note
                    |
              SQLite FTS5 search
```

Permanent notes are human-readable Markdown. SQLite indexes notes, tags, links, aliases, commands, and history so the same memory is both inspectable and searchable.

## Install

Requirements: Python 3.9 or newer, plus Git for session capture. GitHub PR capture additionally needs the GitHub CLI `gh`.

```bash
git clone https://github.com/vetrovk/memoryos.git
cd memoryos
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-use-pep517 -e .
memory --help
```

The repository contains the engine only. Keep your actual memory folder outside the repository.

## Quick Start

This creates a disposable local memory, saves one engineering conclusion, and finds it again.

```bash
export MEMORY_HOME="$PWD/.memory-demo"
memory init

memory learn \
  --project demo \
  --goal "Record the release checklist" \
  --action "Created a local MemoryOS demo" \
  --decision "Keep durable notes as Markdown" \
  --finding "SQLite FTS5 returns the saved conclusion" \
  --actor developer \
  --source manual

memory search "release checklist"
```

The command creates Markdown under `$MEMORY_HOME` and updates its SQLite index immediately. Remove `.memory-demo/` when you no longer need the example.

To preview automatic session capture without saving a note:

```bash
memory learn --from-session --actor codex --source codex --dry-run
```

## Examples

### Search a saved decision

```bash
memory search "SQLFluff"
memory search --project memoryos
```

![Local search result](docs/images/search-result.svg)

### Keep one evolving GitHub PR memory

```bash
memory github-pr https://github.com/pytest-dev/pytest/pull/14702
memory search "github-pr:pytest-dev/pytest#14702"
memory github-pr-deduplicate --dry-run
```

The `github-pr` command reads an accessible PR through `gh`. Repeated captures update the same note, identified as `github-pr:<owner>/<repo>#<number>`, and record its lifecycle in local history.

![GitHub PR memory](docs/images/github-pr-memory.svg)

### Record an OSS investigation

```bash
memory oss-candidate upsert --from-json examples/oss-candidate.json
memory search "oss-candidate:pytest-dev/pytest#14702"
```

`existing_user_pr` and `existing_external_pr` force a `SKIP` verdict. Repeating `INVESTIGATE FURTHER` without `material_change: true` is skipped instead of creating another activity log entry.

![OSS candidate memory](docs/images/oss-candidate-memory.svg)

### Import local agent records

```bash
memory import-pending --dry-run
memory import-pending --path "$HOME/Documents" --days 7
```

Successful files are indexed and moved to a sibling `.memoryos_pending/archive/` folder. Failed JSON files stay in place and are logged locally.

## Activity Log Vs. Memory

Not every command, changed file, or empty session deserves permanent memory. The Curator scores session signals, filters generated files, detects duplicates and near-duplicates, and either saves a permanent note, creates a draft, or explains why it skipped the session.

```bash
memory drafts
memory drafts review
memory curator-stats --days 7
memory cleanup-generated --dry-run
```

## Why This Shape

MemoryOS stores decisions and outcomes rather than a raw conversation history. Markdown remains portable and reviewable in Git or an editor, while SQLite FTS5 makes those notes practical to retrieve during the next task.

## Privacy

- Core data stays on the local filesystem selected by `MEMORY_HOME`, or `~/Memory` by default.
- Do not commit a real memory folder, SQLite database, logs, exports, drafts, pending records, or `.env` files.
- The optional `memory github-pr` command calls your local `gh` CLI. It does not send local MemoryOS notes to GitHub.

See [PRIVACY.md](PRIVACY.md) and [.gitignore](.gitignore).

## Documentation

- [CLI reference](CLI.md)
- [Architecture](ARCHITECTURE.md)
- [Database and search model](DATABASE.md)
- [Plugin API](PLUGIN_API.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Current Status

MemoryOS is an actively used public beta. The command-line workflow and Markdown format are usable now; the Python API and note schema may still change before a stable 1.0 release. Bug reports, focused issues, and small pull requests are welcome.

## Development

```bash
python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/memoryos-pycache python3 -m py_compile memoryos/*.py
python3 -m memoryos.cli doctor --home /tmp/memoryos-doctor
```

The first beta release is planned as `v0.1.0`. It represents a working local engine rather than a long-term compatibility promise.
