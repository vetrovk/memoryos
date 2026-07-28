# MemoryOS

[![CI](https://github.com/vetrovk/memoryos/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vetrovk/memoryos/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/tag/vetrovk/memoryos?label=version)](https://github.com/vetrovk/memoryos/tags)

MemoryOS keeps useful engineering decisions, task outcomes, and investigation results in local Markdown notes that you can search later. It is built around OpenAI Codex workflows, but its CLI and Python API are usable on their own.

## Why use it?

- Keep a resolved investigation from becoming the next task's repeated research.
- Find a past decision, error, PR outcome, or handoff with one local search.
- Read and back up your memory as ordinary Markdown, with SQLite FTS5 only as a local index.
- Capture a Git session automatically when it has useful engineering signal.

## Quick start

Requires Python 3.9 or newer. Git is needed for session capture.

```bash
git clone https://github.com/vetrovk/memoryos.git
cd memoryos
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .

memory init
memory learn --project demo --goal "Record a deployment decision" --decision "Keep rollback steps in the runbook"
memory search "deployment decision"
```

`memory init` creates an empty local memory at `~/Memory` by default. Set `MEMORY_HOME` before running it to use another location.

For a real project, capture a completed session with:

```bash
memory learn --from-session --actor codex --source codex
```

## Connect MemoryOS to Codex

MemoryOS is not built into Codex. Codex follows the instructions in a project's `AGENTS.md`, and those instructions tell it when to search local memory and when to save useful task results.

Generate a project-specific instruction file after installing MemoryOS. Use a temporary filename when the project already has `AGENTS.md`, then merge the generated MemoryOS sections into that file. If it has no `AGENTS.md`, rename the generated file to `AGENTS.md`.

macOS or Linux:

```bash
. .venv/bin/activate
memory agents my-project --target /path/to/my-project/MEMORYOS-AGENTS.md
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
memory agents my-project --target "C:\path\to\my-project\MEMORYOS-AGENTS.md"
```

Make sure the installed `memory` command is available in the environment Codex uses. With these instructions in the project, Codex can search when a task depends on earlier decisions, investigations, errors, or handoff context. It should not run a memory search by rote before every task, and it saves useful experience after completed work.

Continue with the [examples](#examples), [CLI reference](CLI.md), [architecture](ARCHITECTURE.md), and [privacy notes](PRIVACY.md) below. The repository contains the engine only; keep your actual memory folder outside it.

## More detail

### Primary target

- Built for OpenAI Codex.
- Used daily in real engineering workflows with Codex.
- Designed for persistent engineering knowledge, not chat-history storage.

MemoryOS is an independent open-source project. It is not made by, operated by, or affiliated with OpenAI. `OpenAI` and `Codex` are trademarks of OpenAI and are used here only to identify the external tool MemoryOS targets.

### What it does

- Captures structured task learning through a Python API or `memory learn`.
- Curates session records into permanent notes, drafts, or skips when the signal is weak or duplicated.
- Stores GitHub pull-request context and lifecycle updates in one durable note per PR.
- Stores one structured OSS candidate decision per repository issue.
- Imports local `.memoryos_pending/*.json` records from agent workflows.

No cloud service, external API, or LLM is required for the core workflow. GitHub PR capture optionally uses the locally configured `gh` CLI.

### Agent compatibility

| Agent | Current status |
| --- | --- |
| OpenAI Codex | Primary supported workflow; used daily. |
| ChatGPT Codex Work | Used in production through session learning and pending-record import. |
| Claude Code | Not tested by this project. |
| Gemini CLI | Not tested by this project. |
| Other coding agents | Possible through the CLI or Python API, but not a primary focus. |

### How it works

```text
OpenAI Codex
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

![MemoryOS flow](docs/images/memory-flow.svg)

To preview automatic session capture without saving a note:

```bash
memory learn --from-session --actor codex --source codex --dry-run
```

To prepare a compact, read-only handoff for a known project:

```bash
memory context memoryos --session
memory context memoryos --session --limit 8 --max-bytes 4096
```

Session context is opt-in. It uses existing project memory only, writes nothing, starts no hooks or background process, and reports its actual UTF-8 size and truncation state. After a permanent `memory learn --from-session` save, MemoryOS verifies the Markdown file, metadata, SQLite index, and normal search retrieval before reporting success.

If `memory learn --from-session` cannot write the configured memory home because of a readonly database or sandbox boundary, it automatically saves a Codex Work JSON record in `.memoryos_pending/` inside the current project and prints its path. A successful fallback means the pending payload was saved, not that the sandbox wrote directly to the main memory home. Keep the JSON in place until `memory import-pending --path <project-root>` reports success; imported files are archived beside their source. MemoryOS does not send this data to a cloud service.

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

By default, `memory import-pending` recursively searches `~/Documents` for files matching `.memoryos_pending/*.json`. It reads only those matching pending JSON files, not arbitrary documents. To avoid scanning all of `~/Documents`, pass one or more explicit project roots with `--path`.

```bash
memory import-pending --dry-run
memory import-pending --dry-run --path "/path/to/projects"
memory import-pending --path "/path/to/projects" --days 7
```

`--dry-run` does not import, move, or delete files. Successful files are indexed and moved to a sibling `.memoryos_pending/archive/` folder. Failed JSON files stay in place and are logged locally.

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

## Local Data Lifecycle

MemoryOS has no bulk-delete command. Archive or remove local Markdown notes with normal filesystem tools, then run `memory rebuild` to recreate the SQLite index from the remaining notes. Rebuild reports incomplete indexing with a non-zero exit code and leaves failed Markdown notes untouched. Back up important local memory before upgrading a beta release.

## Documentation

- [CLI reference](CLI.md)
- [Architecture](ARCHITECTURE.md)
- [Database and search model](DATABASE.md)
- [Plugin API](PLUGIN_API.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Current Status

MemoryOS v0.2.1 is an actively used public beta. The command-line workflow and Markdown format are usable now; the Python API and note schema may still change before a stable 1.0 release. Bug reports and focused issues through GitHub Issues, plus small pull requests, are welcome.

## Development

```bash
python -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/memoryos-pycache python -m compileall memoryos
python -m memoryos.cli doctor --home /tmp/memoryos-doctor
```
