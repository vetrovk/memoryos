from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from memoryos import Memory
from memoryos.cli import main
from memoryos.config import database_path
from memoryos.models import NoteInput, SessionLearningPreview, TaskLearningInput
from memoryos.util import read_markdown


class SessionContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self.memory.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _add(self, title: str, note_type: str = "session", status: str = "completed", **extra: object) -> Path:
        return self.memory.add(
            NoteInput(
                title=title,
                type=note_type,
                project="alpha",
                status=status,
                text=extra.pop("text", f"Existing summary for {title}."),
                extra_meta=extra,
            )
        )

    def test_session_context_filters_orders_and_includes_relevant_entities(self) -> None:
        self._add("Completed memory")
        legacy_path = self._add("Completed active status", status="active", outcome="completed")
        self._add("Blocked work", status="blocked", outcome="blocked")
        self._add(
            "Relevant PR",
            note_type="github_pr_learning",
            status="open",
            outcome="open",
            identity_key="github-pr:owner/alpha#7",
        )
        self.memory.add(
            NoteInput(
                title="Unrelated PR",
                type="github_pr_learning",
                project="other",
                status="open",
                text="Must not appear.",
                extra_meta={"identity_key": "github-pr:owner/other#9", "outcome": "open"},
            )
        )

        output = self.memory.context("alpha", session=True, limit=10, max_bytes=4096)

        self.assertIsInstance(output, str)
        self.assertIn("## Active or unresolved", output)
        self.assertIn("## Relevant entities", output)
        self.assertIn("github-pr:owner/alpha#7", output)
        self.assertNotIn("Unrelated PR", output)
        self.assertLess(output.index("Blocked work"), output.index("Completed memory"))
        self.assertGreater(output.index("Completed active status"), output.index("## Recent memories"))
        legacy = output[output.index("Completed active status") :]
        self.assertIn("status: completed", legacy)
        self.assertNotIn("status: active", legacy)

        rendered = StringIO()
        with redirect_stdout(rendered):
            code = main(["--home", str(self.home), "context", "alpha", "--session"])
        self.assertEqual(code, 0)
        self.assertNotIn("status: active\n  outcome: completed", rendered.getvalue())
        legacy_meta, _ = read_markdown(legacy_path)
        self.assertEqual(legacy_meta["status"], "active")

    def test_session_context_has_stable_title_tiebreaker(self) -> None:
        self._add("Zulu memory")
        self._add("Alpha memory")

        output = self.memory.context("alpha", session=True, limit=10, max_bytes=4096)

        self.assertLess(output.index("Alpha memory"), output.index("Zulu memory"))

    def test_session_context_enforces_count_and_byte_limits_without_utf8_damage(self) -> None:
        for index in range(5):
            self._add(f"Memory {index} кириллица", text="Полезная запись. " * 30)

        output = self.memory.context("alpha", session=True, limit=2, max_bytes=700)

        self.assertLessEqual(len(output.encode("utf-8")), 700)
        self.assertEqual(output.encode("utf-8").decode("utf-8"), output)
        self.assertIn("truncated: true", output)
        self.assertLessEqual(output.count("[session]"), 2)

    def test_session_context_is_read_only_and_empty_project_is_bounded(self) -> None:
        before = database_path(self.home)
        before_mtime = before.stat().st_mtime_ns
        output = self.memory.context("missing", session=True, max_bytes=1024)

        self.assertIn("project not found", output)
        self.assertLessEqual(len(output.encode("utf-8")), 1024)
        self.assertEqual(before.stat().st_mtime_ns, before_mtime)


class SessionVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.memory = Memory(Path(self.temp.name) / "memory")
        self._git("init")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "MemoryOS Test")
        path = self.root / "src" / "app.py"
        path.parent.mkdir()
        path.write_text("baseline\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

    def _change(self, name: str = "app.py") -> None:
        (self.root / "src" / name).write_text("changed\n", encoding="utf-8")

    def test_permanent_session_save_is_verified_and_searchable(self) -> None:
        self._change()
        self._change("second.py")
        result = self.memory.learn_from_session(project="fixture", goal="Verify session save", cwd=self.root)

        self.assertEqual(result.disposition, "permanent")
        self.assertTrue(result.verification["ok"])
        self.assertTrue(result.verification["searchable"])
        self.assertIn("verified: yes", result.message)
        meta, _ = read_markdown(Path(result.path))
        self.assertEqual(meta["outcome"], "completed")
        self.assertEqual(meta["status"], "completed")

        preview = self.memory.collect_session_learning(project="fixture", goal="Preview completed status", cwd=self.root)
        self.assertEqual(preview.learning.status, "completed")

    def test_open_workflow_keeps_active_status(self) -> None:
        path = self.memory.learn(TaskLearningInput(project="fixture", goal="Open investigation", outcome="open"))

        meta, _ = read_markdown(path)

        self.assertEqual(meta["status"], "active")
        self.assertEqual(meta["outcome"], "open")

    def test_skipped_session_does_not_run_verification(self) -> None:
        result = self.memory.learn_from_session(project="fixture", cwd=self.root)

        self.assertEqual(result.disposition, "skipped")
        self.assertEqual(result.verification, {})

    def test_readonly_session_save_uses_project_pending_fallback(self) -> None:
        self._change()
        with patch.object(self.memory, "learn", side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            result = self.memory.learn_from_session(
                project="fixture",
                goal="Preserve session after readonly failure",
                cwd=self.root,
                test_results="passed",
            )

        pending = Path(result.path)
        self.assertEqual(result.disposition, "pending")
        self.assertTrue(pending.is_file())
        self.assertEqual(pending.parent, (self.root / ".memoryos_pending").resolve())
        payload = json.loads(pending.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["task"], "Preserve session after readonly failure")
        self.assertIn("readonly database", payload["memoryos_error"])

        restored = Memory(Path(self.temp.name) / "restored-memory")
        report = restored.import_pending(paths=[self.root])
        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["archived"], 1)
        self.assertEqual(len(restored.search("Preserve session after readonly failure")), 1)

    def test_readonly_duplicate_lookup_still_reaches_pending_fallback(self) -> None:
        self._change("readonly-lookup.py")
        with patch("memoryos.api.connect_read_only", side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            with patch.object(self.memory, "learn", side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
                result = self.memory.learn_from_session(
                    project="fixture",
                    goal="Preserve session when duplicate lookup is readonly",
                    cwd=self.root,
                    test_results="passed",
                )

        self.assertEqual(result.disposition, "pending")
        self.assertTrue(Path(result.path).is_file())

    def test_cli_treats_successful_pending_fallback_as_recoverable(self) -> None:
        self._change("fallback.py")
        output = StringIO()
        with patch.object(Memory, "learn", side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            with redirect_stdout(output):
                code = main(
                    [
                        "--home",
                        str(self.memory.home),
                        "learn",
                        "--from-session",
                        "--project",
                        "fixture",
                        "--goal",
                        "CLI pending fallback",
                        "--cwd",
                        str(self.root),
                        "--test-results",
                        "passed",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("saved pending session", output.getvalue())
        self.assertEqual(len(list((self.root / ".memoryos_pending").glob("*.json"))), 1)

    def test_permission_error_uses_the_same_pending_fallback(self) -> None:
        self._change("sandbox.py")
        with patch.object(self.memory, "learn", side_effect=PermissionError(1, "Operation not permitted")):
            result = self.memory.learn_from_session(
                project="fixture",
                goal="Preserve session after sandbox refusal",
                cwd=self.root,
                test_results="passed",
            )

        self.assertEqual(result.disposition, "pending")
        self.assertTrue(Path(result.path).is_file())

    def test_doctor_explains_readonly_database_fallback(self) -> None:
        with patch.object(self.memory, "connect", side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            ok, report = self.memory.doctor()

        self.assertFalse(ok)
        self.assertIn(f"SQLite index: {database_path(self.memory.home)}", report)
        self.assertIn("DIRECT_WRITE_UNAVAILABLE", report)
        self.assertIn(".memoryos_pending", report)

    def test_missing_index_row_and_missing_file_fail_verification(self) -> None:
        learning = TaskLearningInput(project="fixture", goal="Unique retrieval marker", findings=["Useful finding."])
        path = self.memory.learn(learning)
        con = self.memory.connect()
        con.execute("DELETE FROM notes WHERE path = ?", (str(path.relative_to(self.memory.home)),))
        con.commit()
        con.close()

        missing_index = self.memory._verify_session_save(path, learning)
        self.assertFalse(missing_index["ok"])
        self.assertFalse(missing_index["indexed"])

        path.unlink()
        missing_file = self.memory._verify_session_save(path, learning)
        self.assertFalse(missing_file["ok"])
        self.assertFalse(missing_file["file"])

    def test_search_verification_requires_the_saved_note_id(self) -> None:
        first = TaskLearningInput(project="fixture", goal="Shared retrieval marker", findings=["First finding."])
        second = TaskLearningInput(project="fixture", goal="Shared retrieval marker", findings=["Second finding."])
        self.memory.learn(first)
        second_path = self.memory.learn(second)

        verification = self.memory._verify_session_save(second_path, second)

        self.assertTrue(verification["searchable"])
        self.assertTrue(verification["ok"])

    def test_draft_uses_file_and_metadata_verification_only(self) -> None:
        learning = TaskLearningInput(project="fixture", goal="Draft verification", outcome="analysis_only")
        preview = SessionLearningPreview(learning=learning, cwd=str(self.root), disposition="draft", reason="low score")
        with patch.object(self.memory, "collect_session_learning", return_value=preview):
            result = self.memory.learn_from_session(project="fixture", cwd=self.root)

        self.assertEqual(result.disposition, "draft")
        self.assertTrue(result.verification["ok"])
        self.assertFalse(result.verification["indexed"])
        self.assertFalse(result.verification["searchable"])

    def test_cli_returns_nonzero_for_verification_failure(self) -> None:
        self._change()
        with patch.object(
            Memory,
            "_verify_session_save",
            return_value={"file": True, "metadata": True, "indexed": False, "searchable": False, "ok": False},
        ):
            code = main(
                [
                    "--home",
                    str(self.memory.home),
                    "learn",
                    "--from-session",
                    "--project",
                    "fixture",
                    "--goal",
                    "CLI verification failure",
                    "--cwd",
                    str(self.root),
                ]
            )

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
