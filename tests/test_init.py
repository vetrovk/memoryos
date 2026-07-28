from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from memoryos import Memory
from memoryos.cli import main
from memoryos.config import FOLDERS, database_path
from memoryos.models import NoteInput
from memoryos.util import read_markdown


class InitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_fresh_init_creates_empty_memory_home(self) -> None:
        report = self.memory.init()

        self.assertEqual(report["created_docs"], 0)
        self.assertEqual(report["created_examples"], 0)
        self.assertEqual(report["indexed"], 0)
        self.assertTrue(database_path(self.home).exists())
        self.assertTrue(all((self.home / folder).is_dir() for folder in FOLDERS))
        self.assertEqual(self.memory.stats()["notes"], 0)
        self.assertEqual(self.memory.search("Example decision"), [])
        self.assertEqual(self.memory.rebuild_report().indexed, 0)
        ok, _ = self.memory.doctor()
        self.assertTrue(ok)

    def test_cli_reports_empty_home_and_next_step(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            code = main(["--home", str(self.home), "init"])

        self.assertEqual(code, 0)
        self.assertIn("initialized: empty memory home", output.getvalue())
        self.assertIn("next: memory learn", output.getvalue())

    def test_generate_agents_includes_required_lookup_and_learning_workflow(self) -> None:
        self.memory.init()
        target = Path(self.temp.name) / "MEMORYOS-AGENTS.md"

        self.memory.generate_agents("demo", target)

        body = target.read_text(encoding="utf-8")
        self.assertIn("memory context demo --session", body)
        self.assertIn('memory search --project demo --query "<task terms>"', body)
        self.assertIn('memory search --project demo --query "commit convention release"', body)
        self.assertIn("Do not edit tracked files or create a commit", body)
        self.assertIn("MemoryOS lookup: found <note title or id>", body)
        self.assertIn("The repository owner authorizes a local-only summary", body)
        self.assertIn("memory learn --from-session --actor codex --source codex", body)

    def test_repeat_init_preserves_existing_user_note(self) -> None:
        self.memory.init()
        note = self.memory.add(NoteInput(title="Keep my decision", type="decision", text="User data must remain intact."))
        before = note.read_bytes()

        report = self.memory.init()

        self.assertEqual(report["created_examples"], 0)
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(len(self.memory.search("Keep my decision")), 1)

    def test_long_unicode_title_keeps_metadata_and_uses_a_safe_filename(self) -> None:
        self.memory.init()
        title = "Подтверждённый результат " * 40

        path = self.memory.add(NoteInput(title=title, type="decision", text="Long titles remain searchable."))

        meta, _ = read_markdown(path)
        self.assertEqual(meta["title"], title)
        self.assertLessEqual(len(path.name.encode("utf-8")), 240)

    def test_legacy_seeded_note_remains_after_init(self) -> None:
        self.memory.init()
        legacy_readme = self.home / "README.md"
        legacy_readme.write_text("Legacy home documentation.\n", encoding="utf-8")
        legacy = self.memory.add(
            NoteInput(
                title="Example decision",
                type="decision",
                project="memoryos",
                tags=["example", "decision"],
                text="Legacy seeded note remains readable.",
                source="system",
            )
        )

        self.memory.init()

        self.assertTrue(legacy.exists())
        self.assertEqual(legacy_readme.read_text(encoding="utf-8"), "Legacy home documentation.\n")
        self.assertEqual(len(self.memory.search("Legacy seeded note")), 1)

    def test_init_help_describes_empty_default(self) -> None:
        output = StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["init", "--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("without adding example notes", output.getvalue())


if __name__ == "__main__":
    unittest.main()
