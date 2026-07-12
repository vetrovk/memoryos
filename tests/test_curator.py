from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from memoryos import Memory


class CuratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.memory = Memory(Path(self.temp.name) / "memory")
        self._git("init")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "MemoryOS Test")
        for index in range(5):
            path = self.root / "src" / f"file_{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("baseline\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_generated_only_is_skipped(self) -> None:
        (self.root / "node_modules" / "pkg").mkdir(parents=True)
        (self.root / "node_modules" / "pkg" / "index.js").write_text("generated\n", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "app.min.js").write_text("generated\n", encoding="utf-8")
        result = self.memory.learn_from_session(project="fixture", cwd=self.root)
        self.assertEqual(result.disposition, "skipped")
        self.assertIn("no useful signal", result.reason)
        stats, _ = self.memory.curator_stats()
        self.assertEqual(stats["skipped_no_useful_signal"], 1)

    def test_only_useful_files_are_saved(self) -> None:
        (self.root / "src" / "file_0.py").write_text("changed\n", encoding="utf-8")
        (self.root / "src" / "file_1.py").write_text("changed\n", encoding="utf-8")
        (self.root / "node_modules" / "pkg").mkdir(parents=True)
        (self.root / "node_modules" / "pkg" / "index.js").write_text("generated\n", encoding="utf-8")
        preview = self.memory.learn_from_session(project="fixture", cwd=self.root, dry_run=True)
        self.assertEqual(preview.useful_changed_files_count, 2)
        self.assertEqual(preview.ignored_changed_files_count, 1)
        self.assertEqual(set(preview.learning.changed_files), {"src/file_0.py", "src/file_1.py"})
        result = self.memory.learn_from_session(project="fixture", cwd=self.root)
        self.assertEqual(result.disposition, "permanent")

    def test_near_duplicate_is_skipped(self) -> None:
        for index in range(5):
            (self.root / "src" / f"file_{index}.py").write_text("first change\n", encoding="utf-8")
        first = self.memory.learn_from_session(project="fixture-near", goal="Update parser", cwd=self.root)
        self.assertEqual(first.disposition, "permanent")
        self._git("add", ".")
        self._git("commit", "-m", "first task")
        for index in range(4):
            (self.root / "src" / f"file_{index}.py").write_text("second change\n", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "bundle.min.js").write_text("generated\n", encoding="utf-8")
        second = self.memory.learn_from_session(project="fixture-near", goal="Update parser", cwd=self.root)
        self.assertEqual(second.disposition, "skipped")
        self.assertTrue(second.reason.startswith("near_duplicate"))
        stats, _ = self.memory.curator_stats()
        self.assertEqual(stats["skipped_near_duplicate"], 1)

    def test_no_changes_requires_meaningful_exception(self) -> None:
        skipped = self.memory.learn_from_session(project="fixture-empty", cwd=self.root)
        self.assertEqual(skipped.disposition, "skipped")
        kept = self.memory.learn_from_session(
            project="fixture-analysis",
            cwd=self.root,
            outcome="analysis_only",
            findings=["Important analysis: production rollback risk identified."],
        )
        self.assertEqual(kept.disposition, "permanent")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
