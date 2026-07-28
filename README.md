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

MemoryOS is not built into Codex. To enable the workflow across Git projects, add the MemoryOS lookup and workflow sections from this repository's [AGENTS.md](AGENTS.md) to your global Codex instructions at `~/.codex/AGENTS.md` once. Codex loads that file when a new session starts.

The global instructions make Codex resolve the real Git root, then use `memory context --cwd` and `memory search --cwd`. That avoids hard-coding a project name and works for old and new repositories without adding a generated file to each project. They do not run for trivial read-only commands, and they do not guarantee that Codex can access memory in every sandbox.

Open Codex with the actual Git checkout as its workspace. A staging copy without `.git`, or an `AGENTS.md` in another folder, cannot reliably identify the project or supply instructions to the session. Restart or create a new Codex session after changing global instructions.

Audit older project-level files before changing any of them:

```bash
memory agents audit --path ~/Documents --path ~/projects
memory agents sync --dry-run --path ~/Documents --path ~/projects
memory agents sync --apply --path ~/Documents --path ~/projects
```

`audit` only reports state. `sync --dry-run` shows safe updates without writing. `sync --apply` updates only MemoryOS-managed blocks or exact legacy templates, creates a backup for a migrated legacy template, and leaves custom or ambiguous `AGENTS.md` files unchanged.

`memory agents <project> --target <new-file>` remains available for a deliberately project-specific template, but it refuses to overwrite an existing instruction file.

With the global instructions installed, Codex performs a required lookup before substantive changes and commits, reports the lookup outcome in commentary, and saves useful local experience after completed work. The local summary must not include credentials, secrets, or full private file contents.

When a retrieved note actually affects a decision or implementation, Codex can record that deliberate use with `memory used <note-id> --project <project> --reason "<short reason>"`. Viewing a result alone is not counted as use.

For more detail, continue with the [examples](#examples), [CLI reference](CLI.md), [architecture](ARCHITECTURE.md), and [privacy notes](PRIVACY.md) below. The repository contains the engine only; keep your actual memory folder outside it.

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

Or derive the project from a real Git working tree:

```bash
memory context --cwd "$(git rev-parse --show-toplevel)" --session
memory search --cwd "$(git rev-parse --show-toplevel)" --query "release notes"
```

Session context is opt-in. It uses existing project memory only, writes nothing, starts no hooks or background process, and reports its actual UTF-8 size and truncation state. After a permanent `memory learn --from-session` save, MemoryOS verifies the Markdown file, metadata, SQLite index, and normal search retrieval before reporting success.

If `memory learn --from-session` cannot write the configured memory home because of a readonly database or sandbox boundary, it automatically saves a Codex Work JSON record in `.memoryos_pending/` inside the current project and prints its path. A successful fallback means the pending payload was saved, not that the sandbox wrote directly to the main memory home. Keep the JSON in place until `memory import-pending --path <project-root>` reports success; imported files are archived beside their source. MemoryOS does not send this data to a cloud service.

Before creating a permanent note, draft, or pending learning record, MemoryOS blocks high-confidence credential formats such as private keys, provider tokens, AWS access keys, and explicit secret assignments. The error identifies only the credential category. If storing such text locally is intentional, repeat the writing command with `--allow-credentials`. Existing notes are not scanned or changed automatically.

### Local usage statistics

MemoryOS records small local usage events in `<memory-home>/_system/events/events-YYYY-MM.jsonl` by default. With the default home, that is `~/Memory/_system/events/`. They include command type, project, normalized query, result count, note IDs and titles returned or opened, learning disposition, and durations. They never include note bodies, prompts, agent answers, credentials, or network transmission.

```bash
memory stats --days 7
memory stats --project my-project --json
memory open <note-id>
memory used <note-id> --project my-project --reason "Applied the release convention"
```

Set `MEMORYOS_TELEMETRY=0` to disable event collection. Remove it with `memory stats --reset --yes`. These metrics measure lookup, opening, and deliberate reported use only. They do not prove that a result improved a decision, saved tokens, or increased engineering quality.

### Optional MCP server

MemoryOS can expose four bounded read-only tools to MCP clients over stdio: `search_memory`, `get_project_context`, `open_memory`, and `get_memory_stats`. It has no write tools, HTTP server, daemon, or network calls.

The optional MCP extra requires Python 3.10 or newer; the base MemoryOS package remains compatible with Python 3.9.

```bash
python -m pip install "memoryos-local[mcp]"
memory mcp serve
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "memoryos": {
      "command": "memory",
      "args": ["mcp", "serve"]
    }
  }
}
```

Use an installed virtual-environment command or its absolute path in the client configuration. MCP output omits memory-home paths and is capped by tool limits.

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
- High-confidence credentials are blocked on new writes by default. MemoryOS does not use a general high-entropy heuristic.
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

MemoryOS v0.5.1 is an actively used public beta. The command-line workflow and Markdown format are usable now; the Python API and note schema may still change before a stable 1.0 release. Bug reports and focused issues through GitHub Issues, plus small pull requests, are welcome.

## Development

```bash
python -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/memoryos-pycache python -m compileall memoryos
python -m memoryos.cli doctor --home /tmp/memoryos-doctor
```
