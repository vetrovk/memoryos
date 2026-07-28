from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from memoryos import Memory


class AgentsAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projects"
        self.root.mkdir()
        self.memory = Memory(Path(self.temp.name) / "memory")
        self.memory.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _repo(self, name: str) -> Path:
        repo = self.root / name
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "remote", "add", "origin", f"https://github.com/example/{name}.git"], cwd=repo, check=True, capture_output=True, text=True)
        return repo

    def _entry(self, entries: list[dict[str, str]], repo: Path) -> dict[str, str]:
        return next(entry for entry in entries if Path(entry["path"]).resolve() == repo.resolve())

    def test_audit_classifies_missing_and_unrelated_files_without_writing(self) -> None:
        missing = self._repo("missing")
        unrelated = self._repo("unrelated")
        (unrelated / "AGENTS.md").write_text("# Project rules\n\nKeep tests focused.\n", encoding="utf-8")

        entries = self.memory.agents_audit([self.root])

        self.assertEqual(self._entry(entries, missing)["state"], "missing")
        self.assertEqual(self._entry(entries, unrelated)["state"], "unrelated")
        self.assertEqual((unrelated / "AGENTS.md").read_text(encoding="utf-8"), "# Project rules\n\nKeep tests focused.\n")

    def test_sync_dry_run_and_apply_update_only_a_managed_block(self) -> None:
        repo = self._repo("managed")
        target = repo / "AGENTS.md"
        self.memory.generate_agents("managed", target)
        original = target.read_text(encoding="utf-8")
        target.write_text(original.replace("Project: `managed`", "Project: `old-name`") + "\n## Local rule\n\nPreserve this.\n", encoding="utf-8")

        dry_run = self._entry(self.memory.sync_agents([self.root], dry_run=True), repo)
        self.assertEqual(dry_run["state"], "managed_stale")
        self.assertIn("would update", dry_run["action"])
        self.assertIn("Project: `old-name`", target.read_text(encoding="utf-8"))

        applied = self._entry(self.memory.sync_agents([self.root], dry_run=False), repo)
        body = target.read_text(encoding="utf-8")
        self.assertEqual(applied["action"], "updated")
        self.assertIn("Project: `managed`", body)
        self.assertIn("## Local rule\n\nPreserve this.", body)

        repeated = self._entry(self.memory.sync_agents([self.root], dry_run=False), repo)
        self.assertEqual(repeated["state"], "managed_current")
        self.assertEqual(repeated["action"], "already current")

    def test_sync_migrates_only_exact_legacy_template_with_backup(self) -> None:
        repo = self._repo("legacy")
        target = repo / "AGENTS.md"
        legacy = f"""# AGENTS.md

## Project

legacy

## MemoryOS Context

- Memory home: `{self.memory.home}`
- Generate context: `memory context legacy`
- Search memory: `memory search --project legacy`
- Rebuild index: `memory rebuild`
- Doctor: `memory doctor`

## Current Memory Stats

- Notes: 0
- Commands: 0
- Links: 0

## Rules

- Work local first.
- Do not send private, work, or health data to external APIs automatically.
- Preserve Markdown frontmatter IDs.
- After useful completed work, record important decisions, errors, commands, and architecture changes with `memory learn --from-session --actor codex --source codex`.
"""
        target.write_text(legacy, encoding="utf-8")

        entry = self._entry(self.memory.sync_agents([self.root], dry_run=False), repo)

        self.assertEqual(entry["action"], "updated")
        self.assertTrue(Path(entry["backup"]).exists())
        self.assertEqual(Path(entry["backup"]).read_text(encoding="utf-8"), legacy)
        self.assertIn("memoryos-managed:start", target.read_text(encoding="utf-8"))

    def test_sync_refuses_unmarked_memoryos_instructions(self) -> None:
        repo = self._repo("conflict")
        target = repo / "AGENTS.md"
        target.write_text("# AGENTS.md\n\n## MemoryOS\n\nCustom workflow.\n", encoding="utf-8")

        entry = self._entry(self.memory.sync_agents([self.root], dry_run=False), repo)

        self.assertEqual(entry["state"], "conflict")
        self.assertEqual(target.read_text(encoding="utf-8"), "# AGENTS.md\n\n## MemoryOS\n\nCustom workflow.\n")

    def test_audit_refuses_incomplete_managed_markers(self) -> None:
        repo = self._repo("incomplete")
        target = repo / "AGENTS.md"
        target.write_text("# AGENTS.md\n\n<!-- memoryos-managed:start -->\n", encoding="utf-8")

        entry = self._entry(self.memory.agents_audit([self.root]), repo)

        self.assertEqual(entry["state"], "conflict")
        self.assertIn("incomplete", entry["action"])
