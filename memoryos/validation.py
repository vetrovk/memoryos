from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import database_path
from .storage import connect_read_only
from .telemetry import iter_events, normalize_query, usage_summary


PROGRAM_FILE = "program.json"
CURATOR_ACTIONS = (
    "curator_saved_permanent",
    "curator_saved_draft",
    "curator_skipped_duplicate",
    "curator_skipped_near_duplicate",
    "curator_skipped_low_quality",
    "curator_skipped_no_useful_signal",
    "curator_promoted_draft",
    "curator_dropped_draft",
)


def maybe_write_snapshot(home: Path, now: datetime | None = None) -> Path | None:
    """Write one due validation snapshot without affecting the caller on failure."""
    directory = home / "_system" / "validation"
    program_path = directory / PROGRAM_FILE
    program = _read_json(program_path)
    if not program or program.get("active") is not True:
        return None

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = _parse_datetime(program.get("started_at"))
    end = _parse_datetime(program.get("ends_at"))
    last = _parse_datetime(program.get("last_snapshot_at"))
    interval_days = _positive_int(program.get("snapshot_interval_days"), default=7)
    if start is None or end is None or current < start or current > end:
        return None
    if last is not None and current < last + timedelta(days=interval_days):
        return None

    try:
        directory.mkdir(parents=True, exist_ok=True)
        lock = directory / ".snapshot.lock"
        lock_fd = _acquire_lock(lock, current)
        if lock_fd is None:
            return None
        try:
            program = _read_json(program_path)
            if not program or program.get("active") is not True:
                return None
            last = _parse_datetime(program.get("last_snapshot_at"))
            if last is not None and current < last + timedelta(days=interval_days):
                return None
            snapshot_path = directory / f"snapshot-{current.date().isoformat()}.json"
            _write_json(snapshot_path, _snapshot(home, program, current))
            program["last_snapshot_at"] = current.isoformat(timespec="seconds")
            _write_json(program_path, program)
            return snapshot_path
        finally:
            os.close(lock_fd)
            try:
                lock.unlink()
            except OSError:
                pass
    except Exception:
        return None


def _snapshot(home: Path, program: dict[str, Any], current: datetime) -> dict[str, object]:
    return {
        "schema_version": 1,
        "captured_at": current.isoformat(timespec="seconds"),
        "validation_window": {
            "start": str(program["started_at"]),
            "end": str(program["ends_at"]),
            "snapshot_interval_days": _positive_int(program.get("snapshot_interval_days"), default=7),
        },
        "telemetry": {
            "all_time_summary": usage_summary(home),
            "window_event_counts": _event_counts(home, str(program["started_at"])),
        },
        "curator": _curator_window(home, str(program["started_at"])),
        "memory": {
            "index_counts": _index_counts(home),
            "draft_markdown_files": len(list((home / "_system" / "drafts").glob("*.md"))),
        },
        "privacy": {
            "note_bodies": "not captured",
            "queries": "not captured",
            "note_titles": "not captured",
            "note_used_reasons": "not captured",
            "quarantine_content": "not captured",
        },
    }


def _event_counts(home: Path, started_at: str) -> dict[str, int]:
    start = _parse_datetime(started_at)
    if start is None:
        return {"total": 0}
    counts: Counter[str] = Counter()
    for event in iter_events(home):
        timestamp = _parse_datetime(event.get("timestamp"))
        if timestamp is not None and timestamp >= start:
            counts[str(event.get("event") or "unknown")] += 1
    return {"total": sum(counts.values()), **dict(sorted(counts.items()))}


def _curator_window(home: Path, started_at: str) -> dict[str, object]:
    counts = {action: 0 for action in CURATOR_ACTIONS}
    if not database_path(home).exists():
        return {"counts": counts, "samples": []}
    con = connect_read_only(home)
    try:
        placeholders = ",".join("?" for _ in CURATOR_ACTIONS)
        rows = con.execute(
            f"SELECT created, action, reason, payload_json FROM history "
            f"WHERE action IN ({placeholders}) AND created >= ? ORDER BY created DESC",
            [*CURATOR_ACTIONS, _sqlite_timestamp(started_at)],
        ).fetchall()
    finally:
        con.close()
    for row in rows:
        counts[str(row["action"])] += 1

    samples: list[dict[str, object]] = []
    saved = skipped = 0
    for row in rows:
        action = str(row["action"])
        duplicate = action in {"curator_skipped_duplicate", "curator_skipped_near_duplicate"}
        is_saved = action in {"curator_saved_permanent", "curator_saved_draft"}
        if not duplicate and is_saved and saved >= 10:
            continue
        if not duplicate and not is_saved and skipped >= 10:
            continue
        if is_saved:
            saved += 1
        elif not duplicate:
            skipped += 1
        payload = _read_json_text(row["payload_json"])
        samples.append(
            {
                "created": str(row["created"]),
                "action": action,
                "reason": normalize_query(str(row["reason"] or ""), limit=240),
                "project": str(payload.get("project") or ""),
                "outcome": str(payload.get("outcome") or ""),
                "quality_score": payload.get("quality_score"),
                "raw_changed_files_count": payload.get("raw_changed_files_count"),
                "useful_changed_files_count": payload.get("useful_changed_files_count"),
                "ignored_changed_files_count": payload.get("ignored_changed_files_count"),
            }
        )
    return {"counts": counts, "samples": samples}


def _index_counts(home: Path) -> dict[str, int]:
    tables = ["notes", "commands", "tags", "links", "aliases", "history"]
    if not database_path(home).exists():
        return {table: 0 for table in tables}
    con = connect_read_only(home)
    try:
        return {table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
    finally:
        con.close()


def _acquire_lock(path: Path, current: datetime) -> int | None:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            if current.timestamp() - path.stat().st_mtime > 300:
                path.unlink()
                return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            pass
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return _read_json_text(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _read_json_text(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _sqlite_timestamp(value: str) -> str:
    parsed = _parse_datetime(value)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M") if parsed is not None else "9999-12-31 23:59"


def _positive_int(value: object, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default
