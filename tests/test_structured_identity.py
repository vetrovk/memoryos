from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memoryos import Memory
from memoryos.models import NoteInput
from memoryos.util import read_markdown


class StructuredIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Memory(Path(self.temp.name) / "memory")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pr_identity_normalizes_url_and_git_suffix(self) -> None:
        self.assertEqual(
            self.memory.github_pr_identity_key("https://github.com/Pytest-Dev/Pytest.git", "#14702"),
            "github-pr:pytest-dev/pytest#14702",
        )

    def test_pr_upsert_keeps_one_note_and_lifecycle_history(self) -> None:
        url = "https://github.com/pytest-dev/pytest/pull/14702"
        first = self.memory.upsert_github_pr(self._pr_data("OPEN", []), url)
        second = self.memory.upsert_github_pr(self._pr_data("OPEN", [{"state": "APPROVED", "author": {"login": "reviewer"}, "body": "Looks good"}]), url)
        merged = self.memory.upsert_github_pr(self._pr_data("CLOSED", [], merged_at="2026-07-18T10:00:00Z"), url)

        self.assertEqual(first.disposition, "permanent")
        self.assertIn("updated", second.message)
        self.assertIn("updated", merged.message)
        results = self.memory.search("github-pr:pytest-dev/pytest#14702", note_type="github_pr_learning")
        self.assertEqual(len(results), 1)
        row = self.memory.note(results[0].id)
        self.assertEqual(row["status"], "merged")
        history = self.memory.history(results[0].id)
        self.assertGreaterEqual(sum(item["action"] == "github_pr_updated" for item in history), 2)

    def test_pr_deduplicate_is_idempotent_in_temporary_memory(self) -> None:
        for suffix in ("first", "second"):
            self.memory.add(
                NoteInput(
                    title=f"PR duplicate {suffix}", type="github_pr_learning", project="pytest",
                    text=f"capture {suffix}", aliases=[f"legacy-{suffix}"],
                    extra_meta={"repository": "pytest-dev/pytest", "pr_number": "14702", "pr_url": "https://github.com/pytest-dev/pytest/pull/14702"},
                )
            )
        plan = self.memory.github_pr_deduplicate()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["identity_key"], "github-pr:pytest-dev/pytest#14702")
        self.memory.github_pr_deduplicate(apply=True)
        self.assertEqual(self.memory.github_pr_deduplicate(), [])

    def test_oss_candidate_upsert_and_search(self) -> None:
        report = self._candidate()
        first = self.memory.upsert_oss_candidate(report)
        second = self.memory.upsert_oss_candidate({**report, "notes": "Reproduced locally", "material_change": True})
        results = self.memory.search("oss-candidate:owner/repo#42", note_type="oss_candidate")
        self.assertEqual(first.disposition, "permanent")
        self.assertIn("updated", second.message)
        self.assertEqual(len(results), 1)

    def test_existing_pr_forces_skip(self) -> None:
        result = self.memory.upsert_oss_candidate({**self._candidate(), "verdict": "TAKE", "existing_user_pr": True})
        result_external = self.memory.upsert_oss_candidate({**self._candidate(), "issue_number": 43, "verdict": "TAKE", "existing_external_pr": True})
        for result, expected in ((result, "existing user PR"), (result_external, "existing external PR")):
            meta, _ = read_markdown(Path(result.path))
            self.assertEqual(meta["verdict"], "SKIP")
            self.assertEqual(meta["verdict_reason"], expected)
            self.assertEqual(result.disposition, "permanent")

    def test_investigate_further_without_change_skips_and_invalid_report_fails(self) -> None:
        report = {**self._candidate(), "investigation_state": "INVESTIGATE FURTHER", "verdict": "NONE"}
        self.memory.upsert_oss_candidate(report)
        skipped = self.memory.upsert_oss_candidate(report)
        self.assertEqual(skipped.disposition, "skipped")
        with self.assertRaises(ValueError):
            self.memory.upsert_oss_candidate({"repository": "owner/repo"})

    @staticmethod
    def _pr_data(state: str, reviews: list[dict[str, object]], merged_at: str = "") -> dict[str, object]:
        return {
            "repository": "Pytest-Dev/Pytest.git", "number": 14702, "title": "Fix doctests", "state": state,
            "mergedAt": merged_at, "body": "Fix doctest locations.", "reviews": reviews, "comments": [],
            "files": [{"path": "src/_pytest/doctest.py"}], "author": {"login": "author"}, "closingIssuesReferences": [],
        }

    @staticmethod
    def _candidate() -> dict[str, object]:
        return {
            "repository": "Owner/Repo", "issue_number": 42, "issue_title": "Fix parser", "issue_url": "https://github.com/owner/repo/issues/42",
            "investigation_state": "NEW", "verdict": "TAKE", "verdict_reason": "Small reproducible bug", "notes": "No existing PR found.",
            "tests_or_reproduction": "pytest tests/test_parser.py", "existing_user_pr": False, "existing_external_pr": False,
        }


if __name__ == "__main__":
    unittest.main()
