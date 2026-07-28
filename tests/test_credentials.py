from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from memoryos import Memory
from memoryos.cli import main
from memoryos.config import events_path
from memoryos.credentials import CredentialDetectedError, detect_credential
from memoryos.models import NoteInput, TaskLearningInput


class CredentialDetectionTests(unittest.TestCase):
    def test_supported_credential_formats_are_detected(self) -> None:
        samples = {
            "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-real-key\n-----END OPENSSH PRIVATE KEY-----",
            "github_token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "openai_api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
            "aws_access_key": "AKIAABCDEFGHIJKLMNOP",
            "explicit_assignment": "access_token = clearly-sensitive-value",
        }

        for expected_kind, text in samples.items():
            with self.subTest(expected_kind):
                finding = detect_credential(text)
                self.assertIsNotNone(finding)
                assert finding
                self.assertEqual(finding.kind, expected_kind)

    def test_ordinary_technical_text_is_not_blocked(self) -> None:
        safe = [
            "Document password authentication and API key rotation.",
            "Use api_key=<value> only in local examples.",
            "The secret remains in the operating system keychain.",
            "AWS access key patterns start with a provider prefix.",
            "GitHub tokens must never be committed.",
        ]

        self.assertTrue(all(detect_credential(text) is None for text in safe))


class CredentialGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "memory"
        self.memory = Memory(self.home)
        self.memory.init()
        self.secret = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _events(self) -> list[dict[str, object]]:
        path = events_path(self.home)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_manual_and_structured_learning_are_blocked_with_safe_reason(self) -> None:
        before = self.memory.stats()["notes"]

        with self.assertRaises(CredentialDetectedError) as manual:
            self.memory.add(NoteInput(title="Unsafe note", type="decision", text=f"token: {self.secret}"))
        with self.assertRaises(CredentialDetectedError) as learned:
            self.memory.learn(TaskLearningInput(project="alpha", goal=f"Rotate {self.secret}"))

        self.assertEqual(self.memory.stats()["notes"], before)
        self.assertNotIn(self.secret, str(manual.exception))
        self.assertNotIn(self.secret, str(learned.exception))
        self.assertIn("credential", str(manual.exception).lower())

    def test_every_supported_format_blocks_storage(self) -> None:
        samples = [
            "-----BEGIN RSA PRIVATE KEY-----\nfixture\n-----END RSA PRIVATE KEY-----",
            "gho_abcdefghijklmnopqrstuvwxyz1234567890",
            "sk-abcdefghijklmnopqrstuvwxyz1234567890",
            "ASIAABCDEFGHIJKLMNOP",
            "password=local-fixture-password",
        ]

        for index, sample in enumerate(samples):
            with self.subTest(index=index):
                with self.assertRaises(CredentialDetectedError):
                    self.memory.add(
                        NoteInput(title=f"Blocked {index}", type="decision", text=sample)
                    )
        self.assertEqual(self.memory.stats()["notes"], 0)

    def test_scanner_failure_blocks_storage(self) -> None:
        with patch("memoryos.credentials.detect_credential", side_effect=RuntimeError("scanner failed")):
            with self.assertRaises(CredentialDetectedError) as blocked:
                self.memory.add(NoteInput(title="Fail closed", type="decision", text="ordinary text"))

        self.assertIn("scan_failed", str(blocked.exception))
        self.assertEqual(self.memory.stats()["notes"], 0)

    def test_explicit_override_allows_intentional_local_save(self) -> None:
        path = self.memory.learn(
            TaskLearningInput(project="alpha", goal=f"Store {self.secret} locally"),
            allow_credentials=True,
        )

        self.assertTrue(path.exists())
        self.assertIn(self.secret, path.read_text(encoding="utf-8"))

    def test_existing_notes_are_not_changed_when_a_new_write_is_blocked(self) -> None:
        existing = self.memory.add(NoteInput(title="Existing", type="decision", text="Keep this byte-for-byte."))
        before = existing.read_bytes()

        with self.assertRaises(CredentialDetectedError):
            self.memory.add(NoteInput(title="Unsafe", type="decision", text=f"api_key={self.secret}"))

        self.assertEqual(existing.read_bytes(), before)

    def test_cli_blocks_by_default_and_requires_explicit_override(self) -> None:
        blocked_output = StringIO()
        with redirect_stdout(blocked_output):
            blocked = main(
                [
                    "--home",
                    str(self.home),
                    "add",
                    "--title",
                    "Guarded CLI note",
                    "--text",
                    f"api_key={self.secret}",
                ]
            )

        allowed_output = StringIO()
        with redirect_stdout(allowed_output):
            allowed = main(
                [
                    "--home",
                    str(self.home),
                    "add",
                    "--title",
                    "Intentional local note",
                    "--text",
                    f"api_key={self.secret}",
                    "--allow-credentials",
                ]
            )

        self.assertEqual(blocked, 1)
        self.assertNotIn(self.secret, blocked_output.getvalue())
        self.assertEqual(allowed, 0)
        self.assertEqual(self.memory.stats()["notes"], 1)

    def test_blocked_session_learning_is_logged_without_the_secret(self) -> None:
        root = Path(self.temp.name) / "repo"
        root.mkdir()
        result = self.memory.learn_from_session(
            project="alpha",
            cwd=root,
            goal=f"Rotate {self.secret}",
            outcome="completed",
        )

        self.assertEqual(result.disposition, "credential_blocked")
        self.assertNotIn(self.secret, result.message)
        events_text = json.dumps(self._events())
        self.assertNotIn(self.secret, events_text)
        self.assertTrue(any(event["event"] == "learning_skipped" for event in self._events()))
        self.assertEqual(self.memory.stats()["notes"], 0)

    def test_telemetry_redacts_secret_in_event_metadata(self) -> None:
        result = self.memory.learn_from_session(
            project=self.secret,
            cwd=Path(self.temp.name),
            goal="Capture safe task",
            outcome="completed",
        )

        self.assertEqual(result.disposition, "credential_blocked")
        events_text = json.dumps(self._events())
        self.assertNotIn(self.secret, events_text)
        self.assertIn("[redacted]", events_text)

    def test_pending_import_is_blocked_and_source_stays_in_place(self) -> None:
        root = Path(self.temp.name) / "project"
        pending = root / ".memoryos_pending"
        pending.mkdir(parents=True)
        source = pending / "unsafe.json"
        source.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "created_at": "2026-07-28T00:00:00Z",
                    "actor": "codex",
                    "source": "codex",
                    "task": "Import guarded learning",
                    "skill": "fixture",
                    "status": "completed",
                    "outcome": {"status": "completed", "summary": f"password={self.secret}"},
                    "artifacts": [],
                    "learning": [],
                    "memoryos_error": "",
                }
            ),
            encoding="utf-8",
        )

        report = self.memory.import_pending(paths=[root])

        self.assertEqual(report["imported"], 0)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["items"][0]["status"], "credential_blocked")
        self.assertTrue(source.exists())
        self.assertNotIn(self.secret, json.dumps(report))
        self.assertEqual(self.memory.stats()["notes"], 0)


if __name__ == "__main__":
    unittest.main()
