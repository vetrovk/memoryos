from __future__ import annotations

import argparse
import json
from dataclasses import fields
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .api import Memory
from .config import OBJECT_TYPES
from .credentials import CredentialDetectedError
from .models import NoteInput, TaskLearningInput
from .util import split_tags


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory", description="MemoryOS local knowledge system.")
    parser.add_argument("--home", default=None, help="Memory folder, default: ~/Memory or MEMORY_HOME")
    try:
        package_version = version("memoryos-local")
    except PackageNotFoundError:
        package_version = "unknown"
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_home(command_parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        command_parser.add_argument("--home", dest="home_after", default=None, help=argparse.SUPPRESS)
        return command_parser

    def add_credential_override(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--allow-credentials",
            action="store_true",
            help="Allow an intentional local save containing a detected credential.",
        )

    add_home(
        sub.add_parser(
            "init",
            help="Initialize an empty memory home without example notes.",
            description="Create the MemoryOS folders and SQLite index without adding example notes.",
        )
    )
    add_home(sub.add_parser("rebuild"))
    add_home(sub.add_parser("index"))
    add_home(sub.add_parser("digest"))
    add_home(sub.add_parser("doctor"))
    stats = add_home(sub.add_parser("stats", help="Show local usage statistics."))
    stats.add_argument("--days", type=int, default=None)
    stats.add_argument("--project", default="")
    stats.add_argument("--json", action="store_true")
    stats.add_argument("--reset", action="store_true", help="Delete local usage event files; requires --yes.")
    stats.add_argument("--yes", action="store_true", help="Confirm --reset.")
    add_home(sub.add_parser("graph"))
    curator_stats = add_home(sub.add_parser("curator-stats"))
    curator_stats.add_argument("--days", type=int, default=None)
    cleanup = add_home(sub.add_parser("cleanup-generated"))
    cleanup.add_argument("--dry-run", action="store_true")
    github_pr = add_home(sub.add_parser("github-pr"))
    github_pr.add_argument("url")
    github_pr.add_argument("--actor", default="agent")
    github_pr.add_argument("--source", default="github")
    add_credential_override(github_pr)
    github_pr_deduplicate = add_home(sub.add_parser("github-pr-deduplicate"))
    github_pr_deduplicate.add_argument("--dry-run", action="store_true", help="Show legacy GitHub PR duplicate groups.")
    github_pr_deduplicate.add_argument("--apply", action="store_true", help="Archive duplicates after merging their captures into a canonical note.")

    oss_candidate = add_home(sub.add_parser("oss-candidate"))
    oss_candidate_sub = oss_candidate.add_subparsers(dest="oss_candidate_command", required=True)
    oss_candidate_upsert = add_home(oss_candidate_sub.add_parser("upsert"))
    oss_candidate_upsert.add_argument("--from-json", required=True, help="Structured OSS candidate JSON report.")
    oss_candidate_upsert.add_argument("--actor", default="agent")
    oss_candidate_upsert.add_argument("--source", default="oss-scout")
    add_credential_override(oss_candidate_upsert)

    drafts = add_home(sub.add_parser("drafts"))
    drafts_sub = drafts.add_subparsers(dest="draft_command")
    add_home(drafts_sub.add_parser("review"))
    promote = add_home(drafts_sub.add_parser("promote"))
    promote.add_argument("id")
    add_credential_override(promote)
    drop = add_home(drafts_sub.add_parser("drop"))
    drop.add_argument("id")

    add = add_home(sub.add_parser("add"))
    add.add_argument("--title", default="Untitled note")
    add.add_argument("--type", choices=OBJECT_TYPES + ["health"], default="idea")
    add.add_argument("--project", default="")
    add.add_argument("--status", default="active")
    add.add_argument("--tags", default="")
    add.add_argument("--text", default="")
    add.add_argument("--source", default="manual")
    add.add_argument("--parent", default="")
    add.add_argument("--related", default="")
    add.add_argument("--aliases", default="")
    add_credential_override(add)

    open_note = add_home(sub.add_parser("open", help="Open a saved note by id."))
    open_note.add_argument("note_id")

    used = add_home(sub.add_parser("used", help="Record that a note influenced the current work."))
    used.add_argument("note_id")
    used.add_argument("--project", default="")
    used.add_argument("--reason", required=True)

    search = add_home(sub.add_parser("search"))
    search.add_argument("query_pos", nargs="?", default="")
    search.add_argument("--query", default="")
    search.add_argument("--project", default="")
    search.add_argument("--cwd", default="", help="Detect the MemoryOS project from this Git working tree.")
    search.add_argument("--tags", default="")
    search.add_argument("--type", default="")
    search.add_argument("--limit", type=int, default=10)

    context = add_home(sub.add_parser("context"))
    context.add_argument("project", nargs="?", default="")
    context.add_argument("--cwd", default="", help="Detect the MemoryOS project from this Git working tree.")
    context.add_argument("--limit", type=int, default=12)
    context.add_argument("--session", action="store_true", help="Print a bounded, read-only session handoff instead of exporting a file.")
    context.add_argument("--max-bytes", type=int, default=6144, help="Maximum UTF-8 bytes for --session output.")

    importer = add_home(sub.add_parser("import"))
    importer.add_argument("path")
    importer.add_argument("--project", default="")
    add_credential_override(importer)

    pending_importer = add_home(sub.add_parser("import-pending"))
    pending_importer.add_argument("--path", action="append", default=[], help="Project root to search; repeatable. Default roots are configured paths or ~/Documents.")
    pending_importer.add_argument("--days", type=int, default=None, help="Only process JSON files modified in the last N days.")
    pending_importer.add_argument("--dry-run", action="store_true", help="Report matching .memoryos_pending JSON files without saving or archiving them.")
    add_credential_override(pending_importer)

    learn = add_home(sub.add_parser("learn"))
    learn.add_argument("--from-json", default="", help="Read learning payload from JSON file, or '-' for stdin.")
    learn.add_argument("--from-session", action="store_true", help="Collect project/session data from the current working tree.")
    learn.add_argument("--from-github-pr", default="", help="Save GitHub PR memory using gh CLI.")
    learn.add_argument("--project", default="")
    learn.add_argument("--goal", default="")
    learn.add_argument("--action", action="append", default=[])
    learn.add_argument("--file", dest="changed_files", action="append", default=[])
    learn.add_argument("--error", action="append", default=[])
    learn.add_argument("--decision", action="append", default=[])
    learn.add_argument("--command-used", dest="commands", action="append", default=[])
    learn.add_argument("--finding", action="append", default=[])
    learn.add_argument("--recommendation", action="append", default=[])
    learn.add_argument("--tags", default="")
    learn.add_argument("--source", default="agent")
    learn.add_argument("--actor", default="agent")
    learn.add_argument("--status", default="active")
    learn.add_argument("--outcome", default="")
    learn.add_argument("--related", default="")
    learn.add_argument("--cwd", default="")
    learn.add_argument("--test-results", default="")
    learn.add_argument("--dry-run", action="store_true")
    add_credential_override(learn)

    agents = add_home(sub.add_parser("agents"))
    agents.add_argument("project", nargs="?", default="")
    agents.add_argument("--target", default="AGENTS.md")
    agents.add_argument("--path", action="append", default=[], help="Root to scan for Git repositories; repeatable.")
    agents.add_argument("--dry-run", action="store_true", help="Show sync changes without writing files.")
    agents.add_argument("--apply", action="store_true", help="Apply safe managed-block updates during agents sync.")

    mcp = add_home(sub.add_parser("mcp", help="Run optional read-only MCP tools over local memory."))
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    add_home(mcp_sub.add_parser("serve", help="Serve read-only MCP tools over stdio."))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    memory = Memory(getattr(args, "home_after", None) or args.home)

    if args.command == "init":
        info = memory.init()
        for key, value in info.items():
            print(f"{key}: {value}")
        if info["indexed"] == 0:
            print("initialized: empty memory home")
            print("next: memory learn --project <project> --goal \"<goal>\"")
        else:
            print("initialized: existing memory preserved")
        return 0
    if args.command in {"rebuild", "index"}:
        report = memory.rebuild_report()
        print(f"scanned: {report.scanned}")
        print(f"indexed: {report.indexed}")
        print(f"skipped: {report.skipped}")
        print(f"failed: {report.failed}")
        for path, reason in report.failures:
            print(f"- failed: {path} ({reason})")
        return 0 if report.failed == 0 else 1
    if args.command == "add":
        note_type = "health_note" if args.type == "health" else args.type
        try:
            path = memory.add(
                NoteInput(
                    title=args.title,
                    type=note_type,
                    project=args.project,
                    status=args.status,
                    tags=split_tags(args.tags),
                    text=args.text,
                    source=args.source,
                    parent=args.parent,
                    related=split_tags(args.related),
                    aliases=split_tags(args.aliases),
                ),
                allow_credentials=args.allow_credentials,
            )
        except CredentialDetectedError as exc:
            print(str(exc))
            return 1
        print(f"Added: {path}")
        return 0
    if args.command == "open":
        try:
            meta, body = memory.open_note(args.note_id)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"# {meta.get('title', args.note_id)}")
        print()
        print(body, end="" if body.endswith("\n") else "\n")
        return 0
    if args.command == "used":
        try:
            memory.mark_note_used(args.note_id, project=args.project, reason=args.reason)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Recorded use: {args.note_id}")
        return 0
    if args.command == "search":
        query = args.query or args.query_pos
        if args.cwd and args.project:
            parser.error("Use either --project or --cwd for search, not both")
        project = memory.project_from_cwd(args.cwd)[1] if args.cwd else args.project
        results = memory.search(query=query, project=project, tags=split_tags(args.tags), note_type=args.type, limit=args.limit)
        if not results:
            print("No results.")
            return 0
        for idx, result in enumerate(results, 1):
            print(f"{idx}. {result.title}")
            print(f"   id: {result.id}")
            print(f"   path: {result.path}")
            print(f"   type: {result.type} | project: {result.project or '-'} | updated: {result.updated or '-'}")
            print(f"   tags: {', '.join(result.tags) or '-'}")
            print(f"   {result.snippet}")
        return 0
    if args.command == "context":
        if args.cwd and args.project:
            parser.error("Use either a project or --cwd for context, not both")
        project = memory.project_from_cwd(args.cwd)[1] if args.cwd else args.project
        if not project:
            parser.error("context requires a project or --cwd")
        try:
            result = memory.context(project, limit=args.limit, session=args.session, max_bytes=args.max_bytes)
        except ValueError as exc:
            parser.error(str(exc))
        if args.session:
            print(result, end="")
        else:
            print(f"Exported: {result}")
        return 0
    if args.command == "import":
        try:
            imported = memory.import_repo(
                Path(args.path),
                project=args.project,
                allow_credentials=args.allow_credentials,
            )
        except CredentialDetectedError as exc:
            print(str(exc))
            return 1
        print(f"Imported files: {imported}")
        return 0
    if args.command == "import-pending":
        try:
            report = memory.import_pending(
                paths=args.path or None,
                days=args.days,
                dry_run=args.dry_run,
                allow_credentials=args.allow_credentials,
            )
        except ValueError as exc:
            parser.error(str(exc))
        for key in ("roots", "found", "imported", "archived", "skipped", "errors", "dry_run"):
            value = report[key]
            print(f"{key}: {', '.join(value) if isinstance(value, list) else value}")
        for item in report["items"]:
            print(f"- {item['status']}: {item['path']}")
            if item.get("error"):
                print(f"  error: {item['error']}")
        return 0 if not report["errors"] else 1
    if args.command == "learn":
        if args.from_github_pr:
            try:
                result = memory.learn_from_github_pr(
                    args.from_github_pr,
                    actor=args.actor,
                    source=args.source,
                    allow_credentials=args.allow_credentials,
                )
            except CredentialDetectedError as exc:
                print(str(exc))
                return 1
            print(result.message)
            return 0 if result.disposition != "skipped" else 1
        if args.from_session:
            result = memory.learn_from_session(
                project=args.project,
                actor=args.actor,
                source=args.source,
                cwd=args.cwd or None,
                dry_run=args.dry_run,
                test_results=args.test_results,
                goal=args.goal,
                outcome=args.outcome,
                findings=args.finding,
                allow_credentials=args.allow_credentials,
            )
            if args.dry_run:
                print(memory.render_session_preview(result))
            else:
                print(result.message)
            return 1 if result.disposition in {"verification_failed", "fallback_failed", "credential_blocked"} else 0
        payload = _learning_payload(args)
        allowed = {field.name for field in fields(TaskLearningInput)}
        try:
            path = memory.learn(
                TaskLearningInput(**{key: value for key, value in payload.items() if key in allowed}),
                allow_credentials=args.allow_credentials,
            )
        except CredentialDetectedError as exc:
            print(str(exc))
            return 1
        print(f"Learned: {path}")
        return 0
    if args.command == "digest":
        print(memory.digest(), end="")
        return 0
    if args.command == "doctor":
        ok, report = memory.doctor()
        print(report, end="")
        return 0 if ok else 1
    if args.command == "stats":
        if args.reset:
            if not args.yes:
                parser.error("memory stats --reset requires --yes")
            print(f"Reset local usage event files: {memory.reset_usage_stats()}")
            return 0
        try:
            report = memory.usage_stats(days=args.days, project=args.project)
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(_render_usage_stats(report))
        return 0
    if args.command == "graph":
        print(memory.graph(), end="")
        return 0
    if args.command == "curator-stats":
        stats, events = memory.curator_stats(days=args.days)
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("\nLast curator decisions:")
        if not events:
            print("No curator audit events.")
        for event in events:
            print(f"- {event['created']} | {event['action']} | {event['reason'] or '-'}")
        return 0
    if args.command == "cleanup-generated":
        if not args.dry_run:
            parser.error("cleanup-generated currently supports only --dry-run")
        for key, value in memory.cleanup_generated_dry_run().items():
            print(f"{key}: {value}")
        return 0
    if args.command == "github-pr":
        try:
            result = memory.learn_from_github_pr(
                args.url,
                actor=args.actor,
                source=args.source,
                allow_credentials=args.allow_credentials,
            )
        except CredentialDetectedError as exc:
            print(str(exc))
            return 1
        print(result.message)
        return 0 if result.disposition != "skipped" else 1
    if args.command == "github-pr-deduplicate":
        if args.dry_run and args.apply:
            parser.error("Use either --dry-run or --apply, not both")
        plans = memory.github_pr_deduplicate(apply=args.apply)
        if not plans:
            print("No GitHub PR duplicates found.")
            return 0
        print("Applied GitHub PR deduplication." if args.apply else "GitHub PR deduplication dry run.")
        for plan in plans:
            print(f"- {plan['identity_key']}")
            print(f"  canonical: {plan['canonical']}")
            for duplicate in plan["duplicates"]:
                print(f"  duplicate: {duplicate}")
            if plan["conflicts"]:
                print(f"  conflicts: {', '.join(plan['conflicts'])}")
        return 0
    if args.command == "oss-candidate":
        try:
            report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"Could not read candidate JSON: {exc}")
        if not isinstance(report, dict):
            parser.error("Candidate JSON must contain an object")
        try:
            result = memory.upsert_oss_candidate(
                report,
                actor=args.actor,
                source=args.source,
                allow_credentials=args.allow_credentials,
            )
        except CredentialDetectedError as exc:
            print(str(exc))
            return 1
        print(result.message)
        return 0 if result.disposition != "skipped" else 1
    if args.command == "drafts":
        draft_command = args.draft_command or "review"
        if draft_command == "review":
            drafts = memory.list_drafts()
            if not drafts:
                print("No drafts.")
                return 0
            for item in drafts:
                print(f"{item['id']} | score={item['quality_score'] or '-'} | outcome={item['outcome'] or '-'} | project={item['project'] or '-'}")
                print(f"  {item['title']}")
                print(f"  reason: {item['reason'] or '-'}")
                print(f"  path: {item['path']}")
            return 0
        if draft_command == "promote":
            try:
                path = memory.promote_draft(args.id, allow_credentials=args.allow_credentials)
            except CredentialDetectedError as exc:
                print(str(exc))
                return 1
            print(f"Promoted: {path}")
            return 0
        if draft_command == "drop":
            print(f"Dropped: {memory.drop_draft(args.id)}")
            return 0
    if args.command == "agents":
        mode = args.project if args.project in {"audit", "sync"} else ""
        if mode:
            if args.target != "AGENTS.md":
                parser.error("--target is only valid when generating an AGENTS.md template")
            if mode == "audit":
                if args.apply or args.dry_run:
                    parser.error("agents audit does not accept --apply or --dry-run")
                entries = memory.agents_audit(args.path or None)
            else:
                if args.apply and args.dry_run:
                    parser.error("Use either --dry-run or --apply for agents sync")
                if not args.apply and not args.dry_run:
                    parser.error("agents sync requires --dry-run or --apply")
                entries = memory.sync_agents(args.path or None, dry_run=not args.apply)
            for entry in entries:
                print(f"{entry['state']}: {entry['path']}")
                print(f"  project: {entry['project']}")
                print(f"  AGENTS.md: {entry['agents_path']}")
                print(f"  action: {entry['action']}")
                if entry.get("backup"):
                    print(f"  backup: {entry['backup']}")
            return 0
        if not args.project:
            parser.error("agents requires a project name, audit, or sync")
        if args.path or args.dry_run or args.apply:
            parser.error("--path, --dry-run, and --apply are only valid for agents audit or sync")
        try:
            target = memory.generate_agents(args.project, args.target)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Generated: {target}")
        return 0
    if args.command == "mcp":
        if args.mcp_command == "serve":
            try:
                from .mcp_server import serve

                serve(memory.home)
            except RuntimeError as exc:
                print(str(exc))
                return 2
            return 0
    parser.error("Unknown command")
    return 2


def _learning_payload(args: argparse.Namespace) -> dict:
    if args.from_json:
        if args.from_json == "-":
            import sys

            raw = sys.stdin.read()
        else:
            raw = Path(args.from_json).expanduser().read_text(encoding="utf-8")
        payload = json.loads(raw)
    else:
        payload = {}
    payload.setdefault("project", args.project)
    payload.setdefault("goal", args.goal)
    payload.setdefault("actions", args.action)
    payload.setdefault("changed_files", args.changed_files)
    payload.setdefault("errors", args.error)
    payload.setdefault("decisions", args.decision)
    payload.setdefault("commands", args.commands)
    payload.setdefault("findings", args.finding)
    payload.setdefault("recommendations", args.recommendation)
    payload.setdefault("tags", split_tags(args.tags))
    payload.setdefault("source", args.source)
    payload.setdefault("actor", args.actor)
    payload.setdefault("status", args.status)
    payload.setdefault("outcome", args.outcome or "completed")
    payload.setdefault("related", split_tags(args.related))
    if not payload.get("goal"):
        raise SystemExit("memory learn requires --goal or JSON field 'goal'.")
    payload["project"] = str(payload.get("project") or "")
    for key in ["actions", "changed_files", "errors", "decisions", "commands", "findings", "recommendations", "tags", "related"]:
        payload[key] = _as_list(payload.get(key))
    return payload


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return split_tags(value)
    return [str(value)]


def _render_usage_stats(report: dict[str, object]) -> str:
    period = report["period"]
    lookups = report["lookups"]
    notes = report["notes"]
    learning = report["learning"]
    assert isinstance(period, dict)
    assert isinstance(lookups, dict)
    assert isinstance(notes, dict)
    assert isinstance(learning, dict)
    lines = ["# MemoryOS local usage statistics", ""]
    period_label = "all time" if period["days"] is None else f"last {period['days']} days"
    lines.append(f"Period: {period_label}")
    lines.append(f"Project: {period['project'] or 'all projects'}")
    lines.extend(["", "## Lookups"])
    lines.append(f"Total: {lookups['total']} | found: {lookups['found']} | empty: {lookups['empty']} | unavailable: {lookups['unavailable']} | errors: {lookups['errors']}")
    lines.append(f"Hit rate: {lookups['hit_rate']}% | average: {lookups['average_duration_ms']} ms | p95: {lookups['p95_duration_ms']} ms")
    lines.extend(["", "## Notes"])
    lines.append(f"Opened: {notes['opened']} | applied: {notes['used']} | unique notes opened repeatedly: {notes['unique_opened_repeatedly']}")
    lines.extend(["", "## Learning"])
    lines.append(f"Attempted: {learning['attempted']} | saved: {learning['saved']} | skipped: {learning['skipped']} | failed: {learning['failed']}")
    lines.extend(["", "## Top projects"])
    projects = report["top_projects"]
    assert isinstance(projects, list)
    lines.extend([f"- {item['project']}: {item['events']} events" for item in projects] or ["- None"])
    lines.extend(["", "## Most reused notes"])
    reused = notes["most_reused"]
    assert isinstance(reused, list)
    lines.extend([f"- {item['note_id']} | {item['title'] or '-'} | {item['opens']} opens" for item in reused] or ["- None"])
    if report["corrupted_events_skipped"]:
        lines.extend(["", f"Corrupted events skipped: {report['corrupted_events_skipped']}"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
