from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memoryos import Memory


class PendingImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projects"
        self.pending = self.root / ".memoryos_pending"
        self.pending.mkdir(parents=True)
        self.memory = Memory(Path(self.temp.name) / "memory")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_import_archives_and_indexes_valid_pending_file(self) -> None:
        source = self._write_pending("valid.json", task="Add pending importer")

        report = self.memory.import_pending(paths=[self.root])

        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["archived"], 1)
        self.assertFalse(source.exists())
        self.assertTrue((self.pending / "archive" / "valid.json").exists())
        results = self.memory.search("pending importer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].project, "fixture-skill")
        ok, _ = self.memory.doctor()
        self.assertTrue(ok)

    def test_reimport_by_hash_does_not_create_duplicate(self) -> None:
        source = self._write_pending("duplicate.json", task="Prevent duplicate import")
        self.memory.import_pending(paths=[self.root])
        archived = self.pending / "archive" / source.name
        source.write_text(archived.read_text(encoding="utf-8"), encoding="utf-8")

        report = self.memory.import_pending(paths=[self.root])

        self.assertEqual(report["imported"], 0)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(len(self.memory.search("Prevent duplicate import")), 1)

    def test_dry_run_keeps_source_file_and_memory_unchanged(self) -> None:
        source = self._write_pending("preview.json", task="Preview pending record")

        report = self.memory.import_pending(paths=[self.root], dry_run=True)

        self.assertEqual(report["imported"], 0)
        self.assertEqual(report["archived"], 0)
        self.assertTrue(source.exists())
        self.assertEqual(self.memory.search("Preview pending record"), [])

    def test_bad_json_does_not_stop_other_files(self) -> None:
        (self.pending / "broken.json").write_text("{broken", encoding="utf-8")
        good = self._write_pending("good.json", task="Keep importing after broken JSON")

        report = self.memory.import_pending(paths=[self.root])

        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["imported"], 1)
        self.assertTrue((self.pending / "broken.json").exists())
        self.assertFalse(good.exists())
        self.assertEqual(len(self.memory.search("broken JSON")), 1)

    def _write_pending(self, name: str, task: str) -> Path:
        path = self.pending / name
        payload = {
            "schema_version": 1,
            "created_at": "2026-07-15T03:30:00Z",
            "actor": "codex",
            "source": "codex",
            "task": task,
            "skill": "fixture-skill",
            "status": "completed",
            "outcome": {"status": "completed", "summary": "Done"},
            "artifacts": ["memoryos/api.py"],
            "learning": ["Imported records should remain local."],
            "memoryos_error": "",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
