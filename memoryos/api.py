from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import hashlib
import shutil
from pathlib import Path

from .config import OBJECT_TYPES, TYPE_FOLDERS, database_path, memory_home
from .models import LearningSaveResult, NoteInput, SearchResult, SessionLearningPreview, TaskLearningInput
from .search import SQLiteFTSSearchProvider
from .storage import add_history, connect, ensure_dirs, init_db, log_error
from .util import build_markdown, date_stamp, now_text, read_markdown, short_snippet, slugify, split_tags, uuid_text


COMMAND_RE = re.compile(r"^\s*(?:[-*]\s*)?(git|docker|systemctl|sqlite3?|python3?|ssh|launchctl|launchd|rsync|make|npm|pnpm|bun|swift|curl)\b.+", re.MULTILINE)
PERMANENT_SCORE_THRESHOLD = 3
SKIP_SCORE_THRESHOLD = -4
TEMP_PROJECTS = {"tmp", "temp", "temporary", "plugin-computer-use-openai-bundled-play"}


class Memory:
    def __init__(self, home: str | Path | None = None) -> None:
        self.home = memory_home(home)

    def connect(self) -> sqlite3.Connection:
        con = connect(self.home)
        init_db(con)
        return con

    def init(self) -> dict[str, int | str]:
        ensure_dirs(self.home)
        con = self.connect()
        con.close()
        created = 0
        created += self._write_if_missing(self.home / "README.md", "# MemoryOS\n\nЛокальная персональная система памяти.\n")
        created += self._write_if_missing(self.home / "PRIVACY.md", "# Privacy\n\nДанные хранятся локально и не отправляются наружу.\n")
        examples = self._create_examples()
        indexed = self.rebuild()
        return {"home": str(self.home), "database": str(database_path(self.home)), "created_docs": created, "created_examples": examples, "indexed": indexed}

    def add(self, note: NoteInput, actor: str = "local", reason: str = "manual add") -> Path:
        if note.type not in TYPE_FOLDERS:
            raise ValueError(f"Unsupported type: {note.type}. Known types: {', '.join(OBJECT_TYPES)}")
        note_id = uuid_text()
        stamp = now_text()
        folder = self.home / TYPE_FOLDERS[note.type]
        if note.project and note.type in {"project", "project_note", "architecture", "repository"}:
            folder = folder / slugify(note.project, "project")
        folder.mkdir(parents=True, exist_ok=True)
        path = self._unique_path(folder, note.title)
        meta = {
            "id": note_id,
            "title": note.title,
            "type": note.type,
            "project": note.project,
            "status": note.status,
            "tags": note.tags,
            "created": stamp,
            "updated": stamp,
            "source": note.source,
            "parent": note.parent,
            "related": note.related,
            "aliases": note.aliases,
        }
        meta.update(note.extra_meta)
        path.write_text(build_markdown(meta, note.text or "TODO: добавить текст заметки."), encoding="utf-8")
        con = self.connect()
        self._upsert_path(con, path)
        add_history(con, note_id, "add", actor=actor, reason=reason, payload={"path": str(path)})
        con.commit()
        con.close()
        return path

    def learn(self, learning: TaskLearningInput) -> Path:
        """Persist a structured task-completion memory and refresh SQLite indexes."""
        title = f"Task learned: {learning.goal}"
        tags = split_tags(["task-learning", "agent-learning", *learning.tags])
        body = self._render_learning_body(learning)
        path = self.add(
            NoteInput(
                title=title,
                type="session",
                project=learning.project,
                status=learning.status,
                tags=tags,
                text=body,
                source=learning.source,
                related=split_tags([*learning.related, *[f"file:{changed_file}" for changed_file in learning.changed_files]]),
                aliases=learning.changed_files,
                extra_meta={"outcome": learning.outcome, "quality_score": learning.quality_score},
            ),
            actor=learning.actor,
            reason="task learning",
        )
        con = self.connect()
        row = con.execute("SELECT id FROM notes WHERE path = ?", (str(path.relative_to(self.home)),)).fetchone()
        note_id = row["id"] if row else None
        if note_id:
            add_history(
                con,
                note_id,
                "learn",
                actor=learning.actor,
                reason="agent task completion memory",
                payload={
                    "project": learning.project,
                    "goal": learning.goal,
                    "changed_files": learning.changed_files,
                    "commands": learning.commands,
                },
            )
            for changed_file in learning.changed_files:
                con.execute(
                    "INSERT INTO links(source_id, target, relation, created) VALUES (?, ?, 'changed_file', ?)",
                    (note_id, changed_file, now_text()),
                )
        con.commit()
        con.close()
        return path

    def learn_from_session(
        self,
        project: str = "",
        actor: str = "agent",
        source: str = "agent",
        cwd: str | Path | None = None,
        dry_run: bool = False,
        test_results: str = "",
        goal: str = "",
        draft: bool = True,
    ) -> LearningSaveResult | SessionLearningPreview:
        """Collect local session context, then persist it through learn()."""
        preview = self.collect_session_learning(
            project=project,
            actor=actor,
            source=source,
            cwd=cwd,
            test_results=test_results,
            goal=goal,
        )
        if dry_run:
            return preview
        if preview.disposition == "skip":
            return LearningSaveResult("skipped", f"skipped: {preview.reason}", quality_score=preview.learning.quality_score, reason=preview.reason)
        if preview.disposition == "draft" and draft:
            path = self.save_draft(preview.learning, reason=preview.reason)
            return LearningSaveResult("draft", f"saved as draft: {path}", str(path), preview.learning.quality_score, preview.reason)
        path = self.learn(preview.learning)
        return LearningSaveResult("permanent", f"saved to permanent memory: {path}", str(path), preview.learning.quality_score, preview.reason)

    def collect_session_learning(
        self,
        project: str = "",
        actor: str = "agent",
        source: str = "agent",
        cwd: str | Path | None = None,
        test_results: str = "",
        goal: str = "",
    ) -> SessionLearningPreview:
        workdir = Path(cwd or Path.cwd()).expanduser().resolve()
        git_root = self._git_output(["rev-parse", "--show-toplevel"], workdir).strip()
        repo_dir = Path(git_root).resolve() if git_root else workdir
        remote = self._git_output(["remote", "get-url", "origin"], repo_dir).strip() if git_root else ""
        status = self._git_output(["status", "--short"], repo_dir).strip() if git_root else ""
        diff_stat = self._git_output(["diff", "--stat"], repo_dir).strip() if git_root else ""
        changed_files = self._git_lines(["diff", "--name-only"], repo_dir) if git_root else []
        changed_files.extend(self._status_files(status))
        changed_files.extend(self._git_lines(["ls-files", "--others", "--exclude-standard"], repo_dir) if git_root else [])
        changed_files = self._dedupe_changed_files(changed_files, repo_dir)
        last_commit = self._git_output(["log", "-1", "--pretty=format:%h %s (%ci)"], repo_dir).strip() if git_root else ""
        detected_test_results = test_results or self._find_test_results_from_logs(repo_dir)
        project_name = project or self._detect_project_name(repo_dir, remote)
        goal_text = goal or self._infer_session_goal(project_name, changed_files, diff_stat, last_commit)
        actions = self._infer_actions(status, diff_stat, changed_files)
        decisions = self._infer_session_decisions(git_root, remote)
        commands = self._infer_recent_commands(repo_dir)
        findings = self._infer_findings(status, diff_stat, last_commit, detected_test_results)
        recommendations = self._infer_recommendations(changed_files, detected_test_results)
        if detected_test_results:
            findings.append(f"Test results: {detected_test_results}")
        errors = self._infer_errors(status, detected_test_results)
        outcome = self._infer_outcome(changed_files, errors, detected_test_results)
        learning = TaskLearningInput(
            project=project_name,
            goal=goal_text,
            actions=actions,
            changed_files=changed_files,
            errors=errors,
            decisions=decisions,
            commands=commands,
            findings=findings,
            recommendations=recommendations,
            tags=["from-session", "task-learning", project_name],
            source=source,
            actor=actor,
            related=[f"git:{remote}"] if remote else [],
            outcome=outcome,
        )
        quality_score, quality_reason = self.score_learning(learning, last_commit=last_commit)
        duplicate_reason = self._duplicate_reason(learning, last_commit)
        if duplicate_reason:
            quality_reason = duplicate_reason
            disposition = "skip"
        elif quality_score <= SKIP_SCORE_THRESHOLD:
            disposition = "skip"
        elif quality_score < PERMANENT_SCORE_THRESHOLD:
            disposition = "draft"
        else:
            disposition = "permanent"
        learning.quality_score = quality_score
        return SessionLearningPreview(
            learning=learning,
            cwd=str(workdir),
            git_root=str(repo_dir) if git_root else "",
            git_remote=remote,
            git_status=status,
            git_diff_stat=diff_stat,
            last_commit=last_commit,
            disposition=disposition,
            reason=quality_reason,
        )

    def score_learning(self, learning: TaskLearningInput, last_commit: str = "") -> tuple[int, str]:
        score = 0
        reasons: list[str] = []
        if learning.changed_files:
            score += 2
            reasons.append("changed files +2")
        if any("test results:" in item.lower() for item in learning.findings):
            score += 3
            reasons.append("explicit or detected test results +3")
        if learning.errors:
            score += 3
            reasons.append("errors found +3")
        meaningful_decisions = [item for item in learning.decisions if not item.startswith("Use local git metadata") and not item.startswith("Treat git working tree") and not item.startswith("Use git remote")]
        if meaningful_decisions:
            score += 2
            reasons.append("decision found +2")
        useful_recs = [item for item in learning.recommendations if not item.startswith("Review the generated session") and not item.startswith("Pass explicit test results")]
        if useful_recs:
            score += 1
            reasons.append("useful recommendation +1")
        if any("github.com" in item or "/pull/" in item for item in [*learning.related, *learning.findings, learning.goal]):
            score += 3
            reasons.append("GitHub PR link found +3")
        if any("review" in item.lower() for item in [*learning.findings, *learning.actions]):
            score += 3
            reasons.append("review comments found +3")
        if learning.outcome == "merged":
            score += 5
            reasons.append("merged PR +5")
        no_signal = not learning.changed_files and not learning.errors and not meaningful_decisions and not any("test results:" in item.lower() for item in learning.findings)
        if no_signal:
            score -= 5
            reasons.append("no changes/tests/errors/decisions -5")
        project_lower = learning.project.lower()
        if project_lower in TEMP_PROJECTS or project_lower.startswith("tmp") or "runtime" in project_lower:
            score -= 5
            reasons.append("temporary/runtime project -5")
        return score, "; ".join(reasons) or "neutral"

    def save_draft(self, learning: TaskLearningInput, reason: str = "") -> Path:
        draft_dir = self.home / "_system" / "drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        stamp = now_text()
        note_id = uuid_text()
        meta = {
            "id": note_id,
            "title": f"Draft learned: {learning.goal}",
            "type": "session_draft",
            "project": learning.project,
            "status": "draft",
            "tags": split_tags(["draft", "task-learning", *learning.tags]),
            "created": stamp,
            "updated": stamp,
            "source": learning.source,
            "parent": "",
            "related": learning.related,
            "aliases": learning.changed_files,
            "outcome": learning.outcome,
            "quality_score": learning.quality_score,
            "curator_reason": reason,
        }
        body = self._render_learning_body(learning)
        path = draft_dir / f"{date_stamp()}-{slugify(learning.goal)}.md"
        counter = 2
        while path.exists():
            path = draft_dir / f"{date_stamp()}-{slugify(learning.goal)}-{counter}.md"
            counter += 1
        path.write_text(build_markdown(meta, body), encoding="utf-8")
        return path

    def list_drafts(self) -> list[dict[str, str]]:
        drafts: list[dict[str, str]] = []
        for path in sorted((self.home / "_system" / "drafts").glob("*.md")):
            try:
                meta, _ = read_markdown(path)
            except Exception:
                continue
            drafts.append({
                "id": str(meta.get("id") or ""),
                "title": str(meta.get("title") or path.stem),
                "project": str(meta.get("project") or ""),
                "quality_score": str(meta.get("quality_score") or ""),
                "outcome": str(meta.get("outcome") or ""),
                "reason": str(meta.get("curator_reason") or ""),
                "path": str(path),
            })
        return drafts

    def promote_draft(self, draft_id: str) -> Path:
        path = self._find_draft(draft_id)
        if not path:
            raise FileNotFoundError(f"Draft not found: {draft_id}")
        meta, content = read_markdown(path)
        meta["status"] = "active"
        meta["type"] = "session"
        meta["title"] = str(meta.get("title") or "Draft learned").replace("Draft learned:", "Task learned:", 1)
        folder = self.home / TYPE_FOLDERS["session"]
        folder.mkdir(parents=True, exist_ok=True)
        target = self._unique_path(folder, str(meta["title"]))
        target.write_text(build_markdown(meta, content), encoding="utf-8")
        con = self.connect()
        self._upsert_path(con, target)
        add_history(con, str(meta.get("id") or ""), "promote_draft", actor="local", reason="draft promoted", payload={"draft": str(path), "target": str(target)})
        con.commit()
        con.close()
        path.unlink()
        return target

    def drop_draft(self, draft_id: str) -> Path:
        path = self._find_draft(draft_id)
        if not path:
            raise FileNotFoundError(f"Draft not found: {draft_id}")
        path.unlink()
        return path

    def learn_from_github_pr(self, url: str, actor: str = "agent", source: str = "github") -> LearningSaveResult:
        if not shutil.which("gh"):
            return LearningSaveResult("skipped", "skipped: GitHub CLI 'gh' not found", reason="gh not found")
        data, error = self._gh_pr_view(url)
        if error:
            return LearningSaveResult("skipped", f"skipped: {error}", reason=error)
        repo = self._repo_from_pr_url(url)
        number = str(data.get("number") or "")
        title = str(data.get("title") or f"PR {number}")
        state = str(data.get("state") or "").lower()
        merged_at = str(data.get("mergedAt") or "")
        outcome = "merged" if merged_at else ("closed" if state == "closed" else "open")
        reviews = data.get("reviews") or []
        comments = data.get("comments") or []
        files = [item.get("path", "") for item in data.get("files") or [] if item.get("path")]
        reviewers = sorted({str((item.get("author") or {}).get("login") or "") for item in reviews if item.get("author")})
        author = str((data.get("author") or {}).get("login") or "")
        issue_links = [str(item.get("url") or "") for item in data.get("closingIssuesReferences") or [] if item.get("url")]
        review_lines = []
        for review in reviews[:20]:
            reviewer = (review.get("author") or {}).get("login") or "unknown"
            state_text = review.get("state") or ""
            body = (review.get("body") or "").strip()
            review_lines.append(f"{reviewer}: {state_text}" + (f" - {body[:300]}" if body else ""))
        comment_lines = []
        for comment in comments[:20]:
            commenter = (comment.get("author") or {}).get("login") or "unknown"
            body = (comment.get("body") or "").strip()
            if body:
                comment_lines.append(f"{commenter}: {body[:300]}")
        quality_score = 3
        if reviews or comments:
            quality_score += 3
        if outcome == "merged":
            quality_score += 5
        if files:
            quality_score += 2
        body = self._render_github_pr_body(
            title=title,
            body=str(data.get("body") or ""),
            outcome=outcome,
            review_lines=review_lines,
            comment_lines=comment_lines,
            files=files,
            issue_links=issue_links,
            url=url,
            repo=repo,
            number=number,
            author=author,
            reviewers=reviewers,
        )
        stamp = now_text()
        path = self.add(
            NoteInput(
                title=f"PR: {title}",
                type="github_pr_learning",
                project=repo.split("/")[-1] if repo else "",
                status="active",
                tags=split_tags(["github", "pr", "review", outcome, repo]),
                text=body,
                source=source,
                related=split_tags([url, *issue_links]),
                aliases=split_tags([url, *files]),
                extra_meta={
                    "repository": repo,
                    "pr_url": url,
                    "pr_number": number,
                    "outcome": outcome,
                    "merged_at": merged_at,
                    "quality_score": quality_score,
                    "created": str(data.get("createdAt") or stamp),
                    "updated": str(data.get("updatedAt") or stamp),
                },
            ),
            actor=actor,
            reason="github pr learning",
        )
        return LearningSaveResult("permanent", f"saved to permanent memory: {path}", str(path), quality_score, "github pr")

    def _gh_pr_view(self, url: str) -> tuple[dict[str, object], str]:
        fields = "number,title,url,state,author,createdAt,updatedAt,mergedAt,body,reviews,comments,files,closingIssuesReferences,reviewDecision,statusCheckRollup"
        try:
            proc = subprocess.run(
                ["gh", "pr", "view", url, "--json", fields],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {}, f"gh failed: {exc}"
        if proc.returncode != 0:
            return {}, (proc.stderr or proc.stdout or "gh pr view failed").strip()
        try:
            return json.loads(proc.stdout), ""
        except json.JSONDecodeError as exc:
            return {}, f"could not parse gh JSON: {exc}"

    def _repo_from_pr_url(self, url: str) -> str:
        match = re.search(r"github\.com[:/]([^/]+)/([^/]+)/pull/\d+", url)
        if not match:
            return ""
        return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"

    def _render_github_pr_body(
        self,
        title: str,
        body: str,
        outcome: str,
        review_lines: list[str],
        comment_lines: list[str],
        files: list[str],
        issue_links: list[str],
        url: str,
        repo: str,
        number: str,
        author: str,
        reviewers: list[str],
    ) -> str:
        def section(title_text: str, lines: list[str], empty: str = "Нет данных.") -> list[str]:
            out = [f"## {title_text}", ""]
            out.extend(f"- {line}" for line in lines if line) if lines else out.append(empty)
            out.append("")
            return out

        lines = [
            f"# PR: {title}",
            "",
            f"- Repository: {repo or '-'}",
            f"- PR number: {number or '-'}",
            f"- Author: {author or '-'}",
            f"- Reviewers: {', '.join(reviewers) if reviewers else '-'}",
            f"- Outcome: {outcome}",
            f"- URL: {url}",
            "",
        ]
        lines.extend(section("Проблема", [body[:1000]] if body else []))
        lines.extend(section("Решение", ["См. описание PR и список измененных файлов."]))
        lines.extend(section("Review", [*review_lines, *comment_lines]))
        lines.extend(section("Что изменили после замечаний", comment_lines, "Явных follow-up изменений из review в MVP не извлечено."))
        lines.extend(section("Итог", [outcome]))
        lines.extend(section("Чему научились", ["PR/review context сохранен как инженерная память для будущего поиска."]))
        lines.extend(section("Связанные файлы", files))
        lines.extend(section("Ссылки", [url, *issue_links]))
        return "\n".join(lines).rstrip() + "\n"

    def note(self, note_id: str) -> sqlite3.Row | None:
        con = self.connect()
        row = con.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        con.close()
        return row

    def project(self, name: str) -> list[SearchResult]:
        return self.search(project=name, limit=50)

    def person(self, name: str) -> list[SearchResult]:
        return self.search(query=name, note_type="person", limit=20)

    def command(self, query: str = "", limit: int = 20) -> list[sqlite3.Row]:
        con = self.connect()
        if query:
            rows = con.execute("SELECT * FROM commands WHERE command LIKE ? ORDER BY created DESC LIMIT ?", (f"%{query}%", limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM commands ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        con.close()
        return rows

    def history(self, note_id: str = "", limit: int = 50) -> list[sqlite3.Row]:
        con = self.connect()
        if note_id:
            rows = con.execute("SELECT * FROM history WHERE note_id = ? ORDER BY created DESC LIMIT ?", (note_id, limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM history ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        con.close()
        return rows

    def search(self, query: str = "", project: str = "", tags: list[str] | None = None, note_type: str = "", limit: int = 10) -> list[SearchResult]:
        con = self.connect()
        results = SQLiteFTSSearchProvider(con, self.home).search(query=query, project=project, tags=tags, note_type=note_type, limit=limit)
        con.close()
        return results

    def rebuild(self) -> int:
        con = self.connect()
        con.execute("DELETE FROM fts_index")
        con.execute("DELETE FROM commands")
        con.execute("DELETE FROM note_tags")
        con.execute("DELETE FROM tags")
        con.execute("DELETE FROM links")
        con.execute("DELETE FROM aliases")
        con.execute("DELETE FROM projects")
        con.execute("DELETE FROM people")
        con.execute("DELETE FROM repositories")
        con.execute("DELETE FROM notes")
        indexed = 0
        for path in self.markdown_files():
            try:
                self._upsert_path(con, path)
                indexed += 1
            except Exception as exc:  # noqa: BLE001 - indexing should continue.
                log_error(self.home, f"index failed for {path}: {exc}")
        add_history(con, None, "rebuild", reason="full index rebuild", payload={"indexed": indexed})
        con.commit()
        con.close()
        return indexed

    def import_path(self, path: Path, project: str = "") -> int:
        path = path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        imported = 0
        candidates: list[Path]
        if path.is_file():
            candidates = [path]
        else:
            names = {"README.md", "README.markdown", "CHANGELOG.md", "TODO.md", "AGENTS.md", "Makefile", "requirements.txt", "pyproject.toml", "Dockerfile"}
            candidates = [item for item in path.rglob("*") if item.is_file() and (item.name in names or item.suffix.lower() == ".md")]
        for source_path in sorted(candidates):
            try:
                if self._alias_exists(str(source_path)):
                    continue
                text = source_path.read_text(encoding="utf-8", errors="replace")
                title = source_path.name if source_path.name != "README.md" else f"README {path.name}"
                note_type = "repository" if source_path.name in {"README.md", "pyproject.toml", "Dockerfile"} else "guide"
                self.add(
                    NoteInput(
                        title=title,
                        type=note_type,
                        project=project or path.name,
                        tags=["import", source_path.suffix.lstrip(".") or source_path.name.lower()],
                        text=f"Imported from: {source_path}\n\n{text}",
                        source="file",
                        aliases=[str(source_path)],
                    ),
                    actor="importer",
                    reason="filesystem import",
                )
                imported += 1
            except Exception as exc:  # noqa: BLE001
                log_error(self.home, f"import failed for {source_path}: {exc}")
        return imported

    def import_repo(self, path: str | Path, project: str = "") -> int:
        return self.import_path(Path(path), project=project)

    def digest(self) -> str:
        today = date_stamp()
        con = self.connect()
        changed = con.execute("SELECT * FROM notes WHERE created LIKE ? OR updated LIKE ? ORDER BY updated DESC", (f"{today}%", f"{today}%")).fetchall()
        decisions = con.execute("SELECT * FROM notes WHERE type = 'decision' AND status = 'active' ORDER BY updated DESC LIMIT 10").fetchall()
        errors = con.execute("SELECT * FROM notes WHERE type = 'error' ORDER BY updated DESC LIMIT 10").fetchall()
        inbox = con.execute("SELECT * FROM notes WHERE path LIKE '00_inbox/%' ORDER BY updated DESC LIMIT 20").fetchall()
        con.close()
        parts = [f"# MemoryOS digest for {today}", ""]
        for title, rows in [("Added Or Changed Today", changed), ("Active Decisions", decisions), ("Recent Errors And Fixes", errors), ("Inbox To Sort", inbox)]:
            parts.extend([f"## {title}", ""])
            if rows:
                for row in rows:
                    parts.append(f"- {row['title']} [{row['type']}] project={row['project'] or '-'} updated={row['updated'] or '-'}")
                    parts.append(f"  {self.home / row['path']}")
            else:
                parts.append("No items.")
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def context(self, project: str, limit: int = 12) -> Path:
        con = self.connect()
        rows = con.execute("SELECT * FROM notes WHERE lower(project) = lower(?) ORDER BY updated DESC", (project,)).fetchall()
        sections = [
            ("Описание проекта", ["project", "project_note"]),
            ("Архитектура", ["architecture"]),
            ("Последние решения", ["decision"]),
            ("Ошибки и исправления", ["error"]),
            ("Команды", ["command", "guide"]),
            ("Roadmap и идеи", ["idea"]),
            ("Репозитории", ["repository"]),
        ]
        out = [f"# Context for {project}", "", f"Generated: {now_text()}", "", "Optimized for LLM handoff.", ""]
        for title, types in sections:
            out.extend([f"## {title}", ""])
            selected = [row for row in rows if row["type"] in types][:limit]
            if not selected:
                out.append("_No notes._\n")
                continue
            for row in selected:
                out.extend(
                    [
                        f"### {row['title']}",
                        f"- ID: {row['id']}",
                        f"- Type: {row['type']}",
                        f"- Updated: {row['updated'] or '-'}",
                        f"- File: {self.home / row['path']}",
                        "",
                        short_snippet(row["content"], size=1000) or "_No content._",
                        "",
                    ]
                )
        related = con.execute("SELECT source_id, target, relation FROM links WHERE source_id IN (SELECT id FROM notes WHERE lower(project) = lower(?)) LIMIT 100", (project,)).fetchall()
        con.close()
        out.extend(["## Связи", ""])
        if related:
            for row in related:
                out.append(f"- {row['source_id']} --{row['relation']}--> {row['target']}")
        else:
            out.append("_No explicit links._")
        export_dir = self.home / "_system" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"context_{slugify(project, 'project')}_{date_stamp()}.md"
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        return path

    def export_context(self, project: str, limit: int = 12) -> Path:
        return self.context(project, limit=limit)

    def stats(self) -> dict[str, int]:
        con = self.connect()
        tables = ["notes", "projects", "people", "repositories", "commands", "tags", "links", "aliases", "history"]
        stats = {table: con.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"] for table in tables}
        con.close()
        return stats

    def graph(self, limit: int = 100) -> str:
        con = self.connect()
        links = con.execute("SELECT source_id, target, relation FROM links LIMIT ?", (limit,)).fetchall()
        con.close()
        if not links:
            return "No graph links yet.\n"
        return "\n".join(f"{row['source_id']} --{row['relation']}--> {row['target']}" for row in links) + "\n"

    def doctor(self) -> tuple[bool, str]:
        problems = 0
        lines = [f"# MemoryOS doctor: {self.home}", "", "## Folders"]
        from .config import FOLDERS

        for folder in FOLDERS:
            path = self.home / folder
            ok = path.exists() and path.is_dir()
            lines.append(f"{'OK' if ok else 'MISSING'} {path}")
            problems += 0 if ok else 1
        lines.extend(["", "## Database"])
        try:
            con = self.connect()
            con.execute("INSERT INTO fts_index(note_id, title, content, project, tags, type, path, updated) VALUES ('doctor', 'fts', 'кириллица check', '', '', '', '', '')")
            con.execute("DELETE FROM fts_index WHERE note_id = 'doctor'")
            con.commit()
            lines.append(f"OK database: {database_path(self.home)}")
            for table, count in self.stats().items():
                lines.append(f"OK {table}: {count}")
            con.close()
        except sqlite3.Error as exc:
            problems += 1
            lines.append(f"ERROR database: {exc}")
        titles: dict[str, list[Path]] = {}
        broken = 0
        for path in self.markdown_files():
            try:
                meta, _ = read_markdown(path)
                title = str(meta.get("title") or path.stem).lower()
                titles.setdefault(title, []).append(path)
                if not meta.get("id"):
                    problems += 1
                    lines.append(f"MISSING_ID {path}")
            except Exception as exc:  # noqa: BLE001
                broken += 1
                problems += 1
                lines.append(f"BROKEN {path}: {exc}")
        duplicates = {title: paths for title, paths in titles.items() if title and len(paths) > 1}
        lines.extend(["", "## Markdown", f"Checked markdown files: {len(self.markdown_files())}", f"Broken markdown files: {broken}", "", "## Duplicate Titles"])
        if duplicates:
            problems += len(duplicates)
            for title, paths in duplicates.items():
                lines.append(f"DUPLICATE {title}: {', '.join(str(path) for path in paths)}")
        else:
            lines.append("OK no duplicate titles")
        lines.extend(["", "## Result", "OK" if problems == 0 else f"Problems found: {problems}"])
        return problems == 0, "\n".join(lines) + "\n"

    def generate_agents(self, project: str, target: str | Path = "AGENTS.md") -> Path:
        path = Path(target).expanduser().resolve()
        stats = self.stats()
        body = f"""# AGENTS.md

## Project

{project}

## MemoryOS Context

- Memory home: `{self.home}`
- Generate context: `memory context {project}`
- Search memory: `memory search --project {project}`
- Rebuild index: `memory rebuild`
- Doctor: `memory doctor`

## Current Memory Stats

- Notes: {stats.get('notes', 0)}
- Commands: {stats.get('commands', 0)}
- Links: {stats.get('links', 0)}

## Rules

- Work local first.
- Do not send private, work, or health data to external APIs automatically.
- Preserve Markdown frontmatter IDs.
- Record important decisions, errors, commands, and architecture changes back into MemoryOS.
"""
        path.write_text(body, encoding="utf-8")
        return path

    def markdown_files(self) -> list[Path]:
        skipped = {self.home / "_system"}
        files: list[Path] = []
        for path in self.home.rglob("*.md"):
            if path.parent == self.home:
                continue
            if any(path == folder or folder in path.parents for folder in skipped):
                continue
            files.append(path)
        return sorted(files)

    def _upsert_path(self, con: sqlite3.Connection, path: Path) -> None:
        meta, content = read_markdown(path)
        note_id = str(meta.get("id") or uuid_text())
        if not meta.get("id"):
            meta["id"] = note_id
            existing = path.read_text(encoding="utf-8")
            path.write_text(build_markdown(self._normalize_meta(meta, path), content or existing), encoding="utf-8")
        normalized = self._normalize_meta(meta, path)
        rel = str(path.relative_to(self.home))
        tags = split_tags(normalized["tags"])
        related = split_tags(normalized["related"])
        aliases = split_tags(normalized["aliases"])
        con.execute(
            """
            INSERT INTO notes(id, path, title, type, project, status, tags_json, created, updated, source, parent, related_json, aliases_json, mtime, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                path=excluded.path, title=excluded.title, type=excluded.type, project=excluded.project,
                status=excluded.status, tags_json=excluded.tags_json, created=excluded.created,
                updated=excluded.updated, source=excluded.source, parent=excluded.parent,
                related_json=excluded.related_json, aliases_json=excluded.aliases_json,
                mtime=excluded.mtime, content=excluded.content
            """,
            (
                note_id,
                rel,
                normalized["title"],
                normalized["type"],
                normalized["project"],
                normalized["status"],
                json.dumps(tags, ensure_ascii=False),
                normalized["created"],
                normalized["updated"],
                normalized["source"],
                normalized["parent"],
                json.dumps(related, ensure_ascii=False),
                json.dumps(aliases, ensure_ascii=False),
                path.stat().st_mtime,
                content,
            ),
        )
        con.execute("DELETE FROM fts_index WHERE note_id = ?", (note_id,))
        con.execute(
            "INSERT INTO fts_index(note_id, title, content, project, tags, type, path, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (note_id, normalized["title"], content, normalized["project"], " ".join(tags + aliases), normalized["type"], rel, normalized["updated"]),
        )
        self._sync_entities(con, note_id, rel, normalized)
        self._sync_tags_links_aliases_commands(con, note_id, tags, related, aliases, content)

    def _sync_entities(self, con: sqlite3.Connection, note_id: str, rel: str, meta: dict[str, object]) -> None:
        if meta["type"] in {"project", "project_note"}:
            con.execute("INSERT OR REPLACE INTO projects(id, title, path, status, updated) VALUES (?, ?, ?, ?, ?)", (note_id, meta["project"] or meta["title"], rel, meta["status"], meta["updated"]))
        if meta["type"] == "person":
            con.execute("INSERT OR REPLACE INTO people(id, title, path, company, updated) VALUES (?, ?, ?, ?, ?)", (note_id, meta["title"], rel, meta["project"], meta["updated"]))
        if meta["type"] == "repository":
            con.execute("INSERT OR REPLACE INTO repositories(id, title, path, project, updated) VALUES (?, ?, ?, ?, ?)", (note_id, meta["title"], rel, meta["project"], meta["updated"]))

    def _sync_tags_links_aliases_commands(self, con: sqlite3.Connection, note_id: str, tags: list[str], related: list[str], aliases: list[str], content: str) -> None:
        con.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        con.execute("DELETE FROM links WHERE source_id = ?", (note_id,))
        con.execute("DELETE FROM aliases WHERE note_id = ?", (note_id,))
        con.execute("DELETE FROM commands WHERE note_id = ?", (note_id,))
        for tag in tags:
            con.execute("INSERT OR IGNORE INTO tags(tag) VALUES (?)", (tag,))
            con.execute("INSERT OR IGNORE INTO note_tags(note_id, tag) VALUES (?, ?)", (note_id, tag))
        for target in related:
            con.execute("INSERT INTO links(source_id, target, relation, created) VALUES (?, ?, 'related', ?)", (note_id, target, now_text()))
        for alias in aliases:
            con.execute("INSERT OR REPLACE INTO aliases(alias, note_id) VALUES (?, ?)", (alias, note_id))
        for match in COMMAND_RE.finditer(content):
            command = re.sub(r"^[-*]\s*", "", match.group(0).strip())
            tool = command.split()[0]
            con.execute("INSERT INTO commands(note_id, command, tool, created) VALUES (?, ?, ?, ?)", (note_id, command, tool, now_text()))

    def _render_learning_body(self, learning: TaskLearningInput) -> str:
        def section(title: str, items: list[str], empty: str = "None.") -> list[str]:
            lines = [f"## {title}", ""]
            if items:
                lines.extend(f"- {item}" for item in items)
            else:
                lines.append(empty)
            lines.append("")
            return lines

        lines = [
            f"# Task Learning: {learning.goal}",
            "",
            f"- Project: {learning.project or '-'}",
            f"- Actor: {learning.actor}",
            f"- Source: {learning.source}",
            f"- Outcome: {learning.outcome}",
            f"- Quality score: {learning.quality_score}",
            f"- outcome: {learning.outcome}",
            f"- quality_score: {learning.quality_score}",
            f"- Captured: {now_text()}",
            "",
        ]
        lines.extend(section("Goal", [learning.goal]))
        lines.extend(section("Completed Actions", learning.actions))
        lines.extend(section("Changed Files", learning.changed_files))
        lines.extend(section("Errors", learning.errors))
        lines.extend(section("Decisions", learning.decisions))
        lines.extend(section("Commands Used", learning.commands))
        lines.extend(section("Findings", learning.findings))
        lines.extend(section("Recommendations", learning.recommendations))
        return "\n".join(lines).rstrip() + "\n"

    def render_session_preview(self, preview: SessionLearningPreview) -> str:
        learning = preview.learning
        lines = [
            "# MemoryOS learn --from-session dry run",
            "",
            f"- CWD: {preview.cwd}",
            f"- Git root: {preview.git_root or '-'}",
            f"- Git remote: {preview.git_remote or '-'}",
            f"- Last commit: {preview.last_commit or '-'}",
            f"- Disposition: {preview.disposition}",
            f"- Quality score: {learning.quality_score}",
            f"- Curator reason: {preview.reason or '-'}",
            "",
            self._render_learning_body(learning),
            "## Git Status",
            "",
            "```text",
            preview.git_status or "No git status available.",
            "```",
            "",
            "## Git Diff Stat",
            "",
            "```text",
            preview.git_diff_stat or "No diff stat available.",
            "```",
            "",
        ]
        return "\n".join(lines)

    def _git_output(self, args: list[str], cwd: Path) -> str:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if proc.returncode != 0:
            return ""
        return proc.stdout.strip()

    def _git_lines(self, args: list[str], cwd: Path) -> list[str]:
        return [line.strip() for line in self._git_output(args, cwd).splitlines() if line.strip()]

    def _status_files(self, status: str) -> list[str]:
        files: list[str] = []
        for line in status.splitlines():
            if len(line) < 4:
                continue
            item = line[3:].strip()
            if " -> " in item:
                old, new = item.split(" -> ", 1)
                files.extend([old.strip(), new.strip()])
            else:
                files.append(item)
        return files

    def _find_test_results_from_logs(self, repo_dir: Path) -> str:
        patterns = ["test", "tests", "passed", "failed", "doctor", "ok"]
        snippets: list[str] = []
        for folder in [repo_dir / "logs", repo_dir / "_system" / "logs"]:
            if not folder.exists() or not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:3]:
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
                except OSError:
                    continue
                for line in lines:
                    clean = line.strip()
                    if clean and any(pattern in clean.lower() for pattern in patterns):
                        snippets.append(f"{path.name}: {clean[:240]}")
                        if len(snippets) >= 5:
                            return " | ".join(snippets)
        return " | ".join(snippets)

    def _dedupe_changed_files(self, files: list[str], repo_dir: Path) -> list[str]:
        clean = sorted({item.strip() for item in files if item.strip()})
        result: list[str] = []
        for item in clean:
            item_path = repo_dir / item
            prefix = item.rstrip("/") + "/"
            if item_path.is_dir() and any(other.startswith(prefix) for other in clean):
                continue
            result.append(item)
        return result

    def _detect_project_name(self, repo_dir: Path, remote: str) -> str:
        pyproject = repo_dir / "pyproject.toml"
        package_json = repo_dir / "package.json"
        if pyproject.exists():
            name = self._read_project_name_from_pyproject(pyproject)
            if name:
                return name
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                if data.get("name"):
                    return str(data["name"])
            except (OSError, json.JSONDecodeError):
                pass
        if remote:
            match = re.search(r"[:/]([^/:]+?)(?:\.git)?$", remote)
            if match:
                return match.group(1)
        readme = next(iter(sorted(repo_dir.glob("README*"))), None)
        if readme:
            try:
                for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
                    clean = line.strip().lstrip("#").strip()
                    if clean:
                        return slugify(clean, repo_dir.name)
            except OSError:
                pass
        return repo_dir.name

    def _read_project_name_from_pyproject(self, path: Path) -> str:
        in_project = False
        try:
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if line == "[project]":
                    in_project = True
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_project = False
                if in_project and line.startswith("name") and "=" in line:
                    return line.split("=", 1)[1].strip().strip("\"'")
        except OSError:
            return ""
        return ""

    def _infer_session_goal(self, project: str, changed_files: list[str], diff_stat: str, last_commit: str) -> str:
        if changed_files:
            return f"Update {project}: {len(changed_files)} changed file(s)"
        if diff_stat:
            return f"Review uncommitted changes in {project}"
        if last_commit:
            return f"Record latest session for {project}"
        return f"Record local session for {project}"

    def _infer_actions(self, status: str, diff_stat: str, changed_files: list[str]) -> list[str]:
        actions: list[str] = []
        if changed_files:
            actions.append(f"Detected changed files: {', '.join(changed_files[:12])}" + (" ..." if len(changed_files) > 12 else ""))
        if status:
            actions.append("Collected git status.")
        if diff_stat:
            actions.append("Collected git diff --stat.")
        if not actions:
            actions.append("Captured session context; no working-tree changes detected.")
        return actions

    def _infer_session_decisions(self, git_root: str, remote: str) -> list[str]:
        decisions = ["Use local git metadata and files only; no external APIs or LLM analysis."]
        if git_root:
            decisions.append("Treat git working tree as the primary source for session evidence.")
        if remote:
            decisions.append("Use git remote only as local project identity metadata.")
        return decisions

    def _infer_recent_commands(self, repo_dir: Path) -> list[str]:
        commands = [
            "git status --short",
            "git diff --stat",
            "git diff --name-only",
            "git log -1 --pretty=format:%h %s (%ci)",
        ]
        log_commands = self._commands_from_logs(repo_dir)
        for command in log_commands:
            if command not in commands:
                commands.append(command)
        return commands[:20]

    def _commands_from_logs(self, repo_dir: Path) -> list[str]:
        commands: list[str] = []
        for folder in [repo_dir / "logs", repo_dir / "_system" / "logs"]:
            if not folder.exists() or not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:3]:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")[-8000:]
                except OSError:
                    continue
                for match in COMMAND_RE.finditer(text):
                    command = re.sub(r"^[-*]\s*", "", match.group(0).strip())
                    if command not in commands:
                        commands.append(command)
        return commands

    def _infer_findings(self, status: str, diff_stat: str, last_commit: str, test_results: str) -> list[str]:
        findings: list[str] = []
        if status:
            findings.append("Working tree has tracked or untracked changes.")
        else:
            findings.append("Working tree has no visible changes from git status.")
        if diff_stat:
            findings.append("Diff stat is available in session metadata.")
        if last_commit:
            findings.append(f"Latest commit: {last_commit}")
        if not test_results:
            findings.append("No explicit test results were provided.")
        return findings

    def _infer_recommendations(self, changed_files: list[str], test_results: str) -> list[str]:
        recommendations = ["Review the generated session note before sharing project context externally."]
        if changed_files:
            recommendations.append("Run project-specific tests before committing these changes.")
        if not test_results:
            recommendations.append("Pass explicit test results to learn_from_session when available.")
        return recommendations

    def _infer_errors(self, status: str, test_results: str) -> list[str]:
        errors: list[str] = []
        lower = test_results.lower()
        if any(word in lower for word in ["failed", "error", "traceback", "ошибка", "недоступ"]):
            errors.append(test_results[:500])
        return errors

    def _infer_outcome(self, changed_files: list[str], errors: list[str], test_results: str) -> str:
        lower = test_results.lower()
        if errors or "failed" in lower or "traceback" in lower:
            return "failed"
        if changed_files:
            return "completed"
        return "no_changes"

    def _changed_files_hash(self, files: list[str]) -> str:
        payload = "\n".join(sorted(files))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _duplicate_reason(self, learning: TaskLearningInput, last_commit: str = "") -> str:
        changed_hash = self._changed_files_hash(learning.changed_files)
        goal_key = re.sub(r"\d+", "N", learning.goal.lower())
        con = self.connect()
        rows = con.execute(
            """
            SELECT title, project, content, created FROM notes
            WHERE lower(project) = lower(?) AND type = 'session'
            ORDER BY created DESC LIMIT 25
            """,
            (learning.project,),
        ).fetchall()
        con.close()
        for row in rows:
            content = row["content"] or ""
            existing_files = self._extract_learning_bullets(content, "Changed Files")
            existing_hash = self._changed_files_hash(existing_files)
            existing_goal = " ".join(self._extract_learning_bullets(content, "Goal")) or row["title"]
            existing_goal_key = re.sub(r"\d+", "N", existing_goal.lower())
            if learning.changed_files and existing_hash == changed_hash:
                return f"duplicate: same project and changed_files hash as {row['created']}"
            if last_commit and last_commit in content:
                return f"duplicate: same latest commit as {row['created']}"
            if goal_key and goal_key == existing_goal_key and not learning.changed_files:
                return f"duplicate: similar goal for project as {row['created']}"
        return ""

    def _extract_learning_bullets(self, content: str, section: str) -> list[str]:
        match = re.search(rf"## {re.escape(section)}\n\n(.*?)(?=\n## |\Z)", content, re.S)
        if not match:
            return []
        block = match.group(1).strip()
        if not block or block == "None.":
            return []
        return [line[2:].strip() for line in block.splitlines() if line.startswith("- ")]

    def _find_draft(self, draft_id: str) -> Path | None:
        draft_dir = self.home / "_system" / "drafts"
        for path in sorted(draft_dir.glob("*.md")):
            try:
                meta, _ = read_markdown(path)
            except Exception:
                continue
            if str(meta.get("id") or "") == draft_id or path.name == draft_id or path.stem == draft_id:
                return path
        return None

    def _normalize_meta(self, meta: dict[str, object], path: Path) -> dict[str, object]:
        stamp = now_text()
        note_type = str(meta.get("type") or "idea")
        if note_type == "health":
            note_type = "health_note"
        return {
            "id": str(meta.get("id") or uuid_text()),
            "title": str(meta.get("title") or path.stem),
            "type": note_type,
            "project": str(meta.get("project") or ""),
            "status": str(meta.get("status") or "active"),
            "tags": split_tags(meta.get("tags")),
            "created": str(meta.get("created") or stamp),
            "updated": str(meta.get("updated") or stamp),
            "source": str(meta.get("source") or "manual"),
            "parent": str(meta.get("parent") or ""),
            "related": split_tags(meta.get("related")),
            "aliases": split_tags(meta.get("aliases")),
        }

    def _create_examples(self) -> int:
        created = 0
        examples = [
            NoteInput(title="Example inbox note", type="idea", status="draft", tags=["example", "inbox"], text="Входящая заметка для последующей сортировки."),
            NoteInput(title="Example decision", type="decision", project="memoryos", tags=["example", "decision"], text="Решение: MemoryOS использует Markdown, SQLite, FTS5, UUID и Python API."),
        ]
        for note in examples:
            folder = self.home / TYPE_FOLDERS[note.type]
            exists = False
            for path in folder.glob("*.md"):
                try:
                    meta, _ = read_markdown(path)
                    exists = str(meta.get("title") or path.stem).lower() == note.title.lower()
                except Exception:
                    exists = path.name.endswith(f"{slugify(note.title)}.md")
                if exists:
                    break
            if not exists:
                self.add(note, actor="system", reason="init example")
                created += 1
        return created

    def _write_if_missing(self, path: Path, text: str) -> int:
        if path.exists():
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return 1

    def _unique_path(self, folder: Path, title: str) -> Path:
        base = f"{date_stamp()}-{slugify(title)}"
        path = folder / f"{base}.md"
        counter = 2
        while path.exists():
            path = folder / f"{base}-{counter}.md"
            counter += 1
        return path

    def _alias_exists(self, alias: str) -> bool:
        con = self.connect()
        exists = con.execute("SELECT 1 FROM aliases WHERE alias = ? LIMIT 1", (alias,)).fetchone() is not None
        con.close()
        return exists
