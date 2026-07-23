from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from memoryos import Memory
from memoryos.cli import main
from memoryos.models import NoteInput


class RebuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self.memory.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_rebuild_reports_partial_failure_without_changing_markdown(self) -> None:
        valid = self.memory.add(NoteInput(title="Valid rebuild conclusion", type="decision", text="Keep the valid note searchable."))
        broken = self.home / "80_errors" / "broken.md"
        broken.write_bytes(b"\xff\xfe not utf-8")
        ignored = self.home / "_system" / "drafts" / "ignored.md"
        ignored.write_bytes(b"\xff\xfe ignored")
        valid_before = valid.read_bytes()
        broken_before = broken.read_bytes()

        report = self.memory.rebuild_report()

        self.assertEqual(report.failed, 1)
        self.assertGreaterEqual(report.indexed, 3)
        self.assertGreaterEqual(report.skipped, 3)
        self.assertEqual(report.failures, [(broken.resolve(), "invalid UTF-8")])
        self.assertEqual(valid.read_bytes(), valid_before)
        self.assertEqual(broken.read_bytes(), broken_before)
        self.assertEqual(len(self.memory.search("Valid rebuild conclusion")), 1)
        self.assertIsInstance(self.memory.rebuild(), int)

    def test_rebuild_reports_complete_success(self) -> None:
        self.memory.add(NoteInput(title="Complete rebuild", type="decision", text="All notes are readable."))

        report = self.memory.rebuild_report()

        self.assertEqual(report.failed, 0)
        self.assertEqual(report.indexed, report.scanned)
        self.assertEqual(report.failures, [])

    def test_rebuild_cli_reports_failure_and_returns_nonzero(self) -> None:
        broken = self.home / "80_errors" / "broken.md"
        broken.write_bytes(b"\xff\xfe private note body")
        output = StringIO()

        with redirect_stdout(output):
            code = main(["--home", str(self.home), "rebuild"])

        rendered = output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("scanned:", rendered)
        self.assertIn("indexed:", rendered)
        self.assertIn("skipped:", rendered)
        self.assertIn("failed: 1", rendered)
        self.assertIn(f"- failed: {broken.resolve()} (invalid UTF-8)", rendered)
        self.assertNotIn("private note body", rendered)

    def test_import_pending_help_explains_default_scope(self) -> None:
        output = StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["import-pending", "--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("~/Documents", output.getvalue())
        self.assertIn(".memoryos_pending JSON", output.getvalue())


if __name__ == "__main__":
    unittest.main()
