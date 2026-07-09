from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

from .api import Memory
from .config import OBJECT_TYPES
from .models import NoteInput, TaskLearningInput
from .util import split_tags


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory", description="MemoryOS local knowledge system.")
    parser.add_argument("--home", default=None, help="Memory folder, default: ~/Memory or MEMORY_HOME")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_home(command_parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        command_parser.add_argument("--home", dest="home_after", default=None, help=argparse.SUPPRESS)
        return command_parser

    add_home(sub.add_parser("init"))
    add_home(sub.add_parser("rebuild"))
    add_home(sub.add_parser("index"))
    add_home(sub.add_parser("digest"))
    add_home(sub.add_parser("doctor"))
    add_home(sub.add_parser("stats"))
    add_home(sub.add_parser("graph"))
    github_pr = add_home(sub.add_parser("github-pr"))
    github_pr.add_argument("url")
    github_pr.add_argument("--actor", default="agent")
    github_pr.add_argument("--source", default="github")

    drafts = add_home(sub.add_parser("drafts"))
    drafts_sub = drafts.add_subparsers(dest="draft_command")
    add_home(drafts_sub.add_parser("review"))
    promote = add_home(drafts_sub.add_parser("promote"))
    promote.add_argument("id")
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

    search = add_home(sub.add_parser("search"))
    search.add_argument("query_pos", nargs="?", default="")
    search.add_argument("--query", default="")
    search.add_argument("--project", default="")
    search.add_argument("--tags", default="")
    search.add_argument("--type", default="")
    search.add_argument("--limit", type=int, default=10)

    context = add_home(sub.add_parser("context"))
    context.add_argument("project")
    context.add_argument("--limit", type=int, default=12)

    importer = add_home(sub.add_parser("import"))
    importer.add_argument("path")
    importer.add_argument("--project", default="")

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
    learn.add_argument("--related", default="")
    learn.add_argument("--cwd", default="")
    learn.add_argument("--test-results", default="")
    learn.add_argument("--dry-run", action="store_true")

    agents = add_home(sub.add_parser("agents"))
    agents.add_argument("project")
    agents.add_argument("--target", default="AGENTS.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    memory = Memory(getattr(args, "home_after", None) or args.home)

    if args.command == "init":
        info = memory.init()
        for key, value in info.items():
            print(f"{key}: {value}")
        return 0
    if args.command in {"rebuild", "index"}:
        print(f"Indexed notes: {memory.rebuild()}")
        return 0
    if args.command == "add":
        note_type = "health_note" if args.type == "health" else args.type
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
            )
        )
        print(f"Added: {path}")
        return 0
    if args.command == "search":
        query = args.query or args.query_pos
        results = memory.search(query=query, project=args.project, tags=split_tags(args.tags), note_type=args.type, limit=args.limit)
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
        print(f"Exported: {memory.context(args.project, limit=args.limit)}")
        return 0
    if args.command == "import":
        print(f"Imported files: {memory.import_repo(Path(args.path), project=args.project)}")
        return 0
    if args.command == "learn":
        if args.from_github_pr:
            result = memory.learn_from_github_pr(args.from_github_pr, actor=args.actor, source=args.source)
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
            )
            if args.dry_run:
                print(memory.render_session_preview(result))
            else:
                print(result.message)
            return 0
        payload = _learning_payload(args)
        allowed = {field.name for field in fields(TaskLearningInput)}
        path = memory.learn(TaskLearningInput(**{key: value for key, value in payload.items() if key in allowed}))
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
        for key, value in memory.stats().items():
            print(f"{key}: {value}")
        return 0
    if args.command == "graph":
        print(memory.graph(), end="")
        return 0
    if args.command == "github-pr":
        result = memory.learn_from_github_pr(args.url, actor=args.actor, source=args.source)
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
            print(f"Promoted: {memory.promote_draft(args.id)}")
            return 0
        if draft_command == "drop":
            print(f"Dropped: {memory.drop_draft(args.id)}")
            return 0
    if args.command == "agents":
        print(f"Generated: {memory.generate_agents(args.project, args.target)}")
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


if __name__ == "__main__":
    raise SystemExit(main())
