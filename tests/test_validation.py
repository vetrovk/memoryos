from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from memoryos.api import Memory
from memoryos.cli import main
from memoryos.validation import maybe_write_snapshot


class LazyValidationSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        Memory(self.home).init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def activate(self, last_snapshot_at: str = "2026-08-07T00:00:00+00:00", active: bool = True) -> None:
        directory = self.home / "_system" / "validation"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "program.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "active": active,
                    "started_at": "2026-08-07T00:00:00+00:00",
                    "ends_at": "2026-09-07T23:59:59+00:00",
                    "snapshot_interval_days": 7,
                    "last_snapshot_at": last_snapshot_at,
                }
            ),
            encoding="utf-8",
        )

    def test_due_snapshot_is_created_once_and_updates_metadata(self) -> None:
        self.activate()
        now = datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
        path = maybe_write_snapshot(self.home, now=now)
        self.assertEqual(path, self.home / "_system" / "validation" / "snapshot-2026-08-14.json")
        self.assertTrue(path.exists())
        self.assertIsNone(maybe_write_snapshot(self.home, now=now))
        program = json.loads((self.home / "_system" / "validation" / "program.json").read_text(encoding="utf-8"))
        self.assertEqual(program["last_snapshot_at"], "2026-08-14T00:00:00+00:00")

    def test_inactive_program_does_not_write(self) -> None:
        self.activate(active=False)
        result = maybe_write_snapshot(self.home, now=datetime(2026, 8, 14, tzinfo=timezone.utc))
        self.assertIsNone(result)
        self.assertFalse((self.home / "_system" / "validation" / "snapshot-2026-08-14.json").exists())

    def test_missing_program_does_not_create_validation_state(self) -> None:
        result = maybe_write_snapshot(self.home, now=datetime(2026, 8, 14, tzinfo=timezone.utc))
        self.assertIsNone(result)
        self.assertFalse((self.home / "_system" / "validation").exists())

    def test_cli_runs_lazy_check_without_changing_command_output(self) -> None:
        self.activate()
        with patch("memoryos.cli.maybe_write_snapshot", return_value=None) as snapshot:
            self.assertEqual(main(["--home", str(self.home), "stats", "--json"]), 0)
        snapshot.assert_called_once_with(self.home.resolve())
