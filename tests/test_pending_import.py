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

    def test_legacy_codex_work_v1_envelopes_are_imported(self) -> None:
        (self.pending / "format-v1.json").write_text(
            json.dumps(
                {
                    "format": "codex-work",
                    "version": 1,
                    "actor": "codex",
                    "source": "codex",
                    "title": "Legacy title",
                    "summary": "Legacy summary",
                    "artifacts": ["memoryos/api.py"],
                    "verification": ["Tests passed"],
                }
            ),
            encoding="utf-8",
        )
        (self.pending / "schema-v1.json").write_text(
            json.dumps(
                {
                    "schema": "codex-work",
                    "version": 1,
                    "actor": "codex",
                    "source": "codex",
                    "summary": "Legacy schema summary",
                    "outcome": "Completed investigation",
                    "sources": [{"url": "https://example.invalid/source"}],
                }
            ),
            encoding="utf-8",
        )

        report = self.memory.import_pending(paths=[self.root])

        self.assertEqual(report["imported"], 2)
        self.assertEqual(report["errors"], 0)
        self.assertTrue(any(result.title.endswith("Legacy title") for result in self.memory.search("Legacy title")))
        self.assertTrue(any("Legacy schema summary" in result.snippet for result in self.memory.search("Legacy schema summary")))
        self.assertTrue((self.pending / "archive" / "format-v1.json").exists())
        self.assertTrue((self.pending / "archive" / "schema-v1.json").exists())

    def test_unknown_pending_schema_remains_unimported(self) -> None:
        source = self.pending / "unknown.json"
        source.write_text(json.dumps({"schema_version": 2, "task": "Do not import"}), encoding="utf-8")

        report = self.memory.import_pending(paths=[self.root])

        self.assertEqual(report["errors"], 1)
        self.assertTrue(source.exists())

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
