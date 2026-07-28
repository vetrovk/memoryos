from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from memoryos import Memory
from memoryos.cli import main
from memoryos.mcp_server import MemoryMCPService
from memoryos.models import NoteInput


class MCPServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self.memory.init()
        self.path = self.memory.add(NoteInput(title="MCP decision", project="alpha", type="decision", text="Keep MCP read-only. " * 100))
        self.note_id = self.memory._note_id_for_path(self.path)
        assert self.note_id
        self.service = MemoryMCPService(self.home)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_search_is_project_filtered_and_bounded_without_paths(self) -> None:
        self.memory.add(NoteInput(title="Other decision", project="beta", type="decision", text="Not alpha."))
        result = self.service.search_memory("decision", project="alpha", limit=50, max_bytes=1024)

        self.assertEqual(result["project"], "alpha")
        self.assertEqual(len(result["results"]), 1)
        self.assertNotIn("path", result["results"][0])

    def test_empty_and_missing_note_are_safe(self) -> None:
        self.assertEqual(self.service.search_memory("missing", project="alpha")["results"], [])
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.open_memory("not-a-note")

    def test_open_and_context_are_bounded_and_read_only(self) -> None:
        before = list((self.home / "_system" / "events").glob("*.jsonl")) if (self.home / "_system" / "events").exists() else []
        note = self.service.open_memory(self.note_id, max_bytes=512)
        context = self.service.get_project_context(project="alpha", max_bytes=512)

        self.assertLessEqual(len(str(note).encode("utf-8")), 700)
        self.assertLessEqual(len(str(context).encode("utf-8")), 700)
        after = list((self.home / "_system" / "events").glob("*.jsonl")) if (self.home / "_system" / "events").exists() else []
        self.assertEqual(before, after)

    def test_stats_has_no_write_operations(self) -> None:
        report = self.service.get_memory_stats(project="alpha")
        self.assertIn("index", report)
        self.assertIn("usage", report)
        self.assertNotIn("learn", " ".join(MemoryMCPService.__dict__.keys()))

    def test_base_cli_reports_missing_optional_dependency(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--home", str(self.home), "mcp", "serve"])
        self.assertEqual(code, 2)
        self.assertIn("memoryos-local[mcp]", output.getvalue())
