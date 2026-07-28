from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from memoryos import Memory
from memoryos.cli import main
from memoryos.config import events_path
from memoryos.models import NoteInput
from memoryos.telemetry import record_event


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self.memory.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _events(self) -> list[dict[str, object]]:
        path = events_path(self.home)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_search_found_and_empty_create_sanitized_lookup_events(self) -> None:
        self.memory.add(NoteInput(title="Release decision", project="alpha", type="decision", text="Keep the release local."))

        found = self.memory.search("release", project="alpha")
        empty = self.memory.search("token=abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz", project="alpha")

        self.assertEqual(len(found), 1)
        self.assertEqual(empty, [])
        completed = [item for item in self._events() if item["event"] == "lookup_completed"]
        self.assertEqual([item["status"] for item in completed], ["found", "empty"])
        self.assertEqual(completed[0]["results"][0]["title"], "Release decision")
        self.assertIn("[redacted]", completed[1]["query"])

    def test_open_and_used_are_counted_separately(self) -> None:
        path = self.memory.add(NoteInput(title="Commit rule", project="alpha", type="decision", text="Use the documented prefix."))
        note_id = self.memory._note_id_for_path(path)
        assert note_id

        self.memory.open_note(note_id)
        self.memory.open_note(note_id)
        self.memory.mark_note_used(note_id, project="alpha", reason="Applied the commit prefix")

        report = self.memory.usage_stats(project="alpha")
        self.assertEqual(report["notes"]["opened"], 2)
        self.assertEqual(report["notes"]["used"], 1)
        self.assertEqual(report["notes"]["unique_opened_repeatedly"], 1)
        self.assertEqual(report["notes"]["most_reused"][0]["note_id"], note_id)

    def test_disabled_telemetry_writes_nothing(self) -> None:
        with patch.dict(os.environ, {"MEMORYOS_TELEMETRY": "0"}):
            self.memory.search("anything", project="alpha")

        self.assertEqual(self._events(), [])
        self.assertFalse(events_path(self.home).parent.exists())

    def test_event_write_failure_does_not_break_lookup(self) -> None:
        with patch("memoryos.telemetry.os.open", side_effect=OSError("readonly")):
            self.assertEqual(self.memory.search("anything", project="alpha"), [])

    def test_corrupted_event_is_skipped_and_days_project_filter_applies(self) -> None:
        path = events_path(self.home)
        path.parent.mkdir(parents=True, exist_ok=True)
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        current = datetime.now(timezone.utc).isoformat()
        path.write_text(
            "not json\n"
            + json.dumps({"timestamp": old, "event": "lookup_completed", "project": "alpha", "status": "found", "duration_ms": 2})
            + "\n"
            + json.dumps({"timestamp": current, "event": "lookup_completed", "project": "beta", "status": "empty", "duration_ms": 4})
            + "\n",
            encoding="utf-8",
        )

        report = self.memory.usage_stats(days=7, project="beta")

        self.assertEqual(report["lookups"]["total"], 1)
        self.assertEqual(report["lookups"]["empty"], 1)

    def test_cli_json_and_reset_require_confirmation(self) -> None:
        self.memory.search("anything", project="alpha")
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--home", str(self.home), "stats", "--json"])
        self.assertEqual(code, 0)
        self.assertIn('"lookups"', output.getvalue())

        with self.assertRaises(SystemExit):
            main(["--home", str(self.home), "stats", "--reset"])
        self.assertTrue(events_path(self.home).exists())

        with redirect_stdout(output):
            code = main(["--home", str(self.home), "stats", "--reset", "--yes"])
        self.assertEqual(code, 0)
        self.assertFalse(events_path(self.home).exists())

    def test_parallel_writes_remain_individual_json_lines(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda index: record_event(self.home, "lookup_started", {"project": "alpha", "index": index}), range(40)))

        self.assertEqual(len(self._events()), 40)


class SessionLearningTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self._git("init")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "MemoryOS Test")
        (self.root / "app.py").write_text("baseline\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

    def test_session_learning_saved_and_skipped_are_logged(self) -> None:
        (self.root / "app.py").write_text("changed\n", encoding="utf-8")
        saved = self.memory.learn_from_session(project="alpha", cwd=self.root, goal="Record telemetry")
        skipped = self.memory.learn_from_session(project="alpha", cwd=self.root)

        self.assertEqual(saved.disposition, "permanent")
        self.assertEqual(skipped.disposition, "skipped")
        events = [json.loads(line) for line in events_path(self.home).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(event["event"] == "learning_attempted" for event in events), 2)
        self.assertEqual(sum(event["event"] == "learning_saved" for event in events), 1)
        self.assertEqual(sum(event["event"] == "learning_skipped" for event in events), 1)
