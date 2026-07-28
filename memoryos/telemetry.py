from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import events_path
from .credentials import detect_credential


SENSITIVE_QUERY_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|token|password|secret|credential)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_/-]{48,}\b"),
)
DISABLED_VALUES = {"0", "false", "no", "off"}


def telemetry_enabled() -> bool:
    return os.environ.get("MEMORYOS_TELEMETRY", "1").strip().lower() not in DISABLED_VALUES


def normalize_query(query: str, limit: int = 160) -> str:
    value = " ".join(str(query).split()).lower()
    for pattern in SENSITIVE_QUERY_PATTERNS:
        value = pattern.sub("[redacted]", value)
    return value[:limit]


def record_event(home: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    """Append one local event without allowing telemetry failures to affect MemoryOS."""
    if not telemetry_enabled():
        return
    event = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event_type}
    try:
        event.update(_sanitize_event_value(payload or {}))
    except Exception:
        return
    encoded = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        path = events_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except OSError:
        return


def _sanitize_event_value(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted]" if detect_credential(value) else value
    if isinstance(value, dict):
        return {key: _sanitize_event_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_event_value(item) for item in value]
    return value


def iter_events(home: Path) -> Iterable[dict[str, Any]]:
    directory = events_path(home).parent
    if not directory.exists():
        return
    for path in sorted(directory.glob("events-*.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict) and isinstance(event.get("timestamp"), str):
                        yield event
        except OSError:
            continue


def reset_events(home: Path) -> int:
    directory = events_path(home).parent
    removed = 0
    try:
        for path in directory.glob("events-*.jsonl"):
            path.unlink()
            removed += 1
    except OSError:
        return removed
    return removed


def usage_summary(home: Path, days: int | None = None, project: str = "") -> dict[str, Any]:
    if days is not None and days < 0:
        raise ValueError("days must be zero or greater")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days is not None else None
    selected: list[dict[str, Any]] = []
    corrupted = 0
    for event in iter_events(home):
        try:
            timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            corrupted += 1
            continue
        if cutoff and timestamp < cutoff:
            continue
        if project and str(event.get("project") or "").lower() != project.lower():
            continue
        selected.append(event)

    completed = [event for event in selected if event.get("event") == "lookup_completed"]
    statuses = Counter(str(event.get("status") or "error") for event in completed)
    durations = sorted(int(event["duration_ms"]) for event in completed if isinstance(event.get("duration_ms"), (int, float)))
    opened = [event for event in selected if event.get("event") == "note_opened"]
    used = [event for event in selected if event.get("event") == "note_used"]
    learning = [event for event in selected if str(event.get("event", "")).startswith("learning_")]
    note_counts = Counter(str(event.get("note_id")) for event in opened if event.get("note_id"))
    project_counts = Counter(str(event.get("project")) for event in selected if event.get("project"))
    return {
        "period": {"days": days, "project": project or None, "events": len(selected)},
        "lookups": {
            "total": len(completed),
            "found": statuses["found"],
            "empty": statuses["empty"],
            "unavailable": statuses["unavailable"],
            "errors": statuses["error"],
            "hit_rate": round((statuses["found"] / len(completed) * 100) if completed else 0.0, 1),
            "average_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0.0,
            "p95_duration_ms": durations[math.ceil(len(durations) * 0.95) - 1] if durations else 0,
        },
        "notes": {
            "opened": len(opened),
            "used": len(used),
            "unique_opened_repeatedly": sum(count >= 2 for count in note_counts.values()),
            "most_reused": [
                {"note_id": note_id, "title": _note_title(opened, note_id), "opens": count}
                for note_id, count in note_counts.most_common(10)
            ],
        },
        "learning": {
            "attempted": sum(event.get("event") == "learning_attempted" for event in learning),
            "saved": sum(event.get("event") == "learning_saved" for event in learning),
            "skipped": sum(event.get("event") == "learning_skipped" for event in learning),
            "failed": sum(event.get("event") == "learning_failed" for event in learning),
        },
        "top_projects": [{"project": name, "events": count} for name, count in project_counts.most_common(10)],
        "corrupted_events_skipped": corrupted,
    }


def _note_title(events: list[dict[str, Any]], note_id: str) -> str:
    for event in reversed(events):
        if event.get("note_id") == note_id:
            return str(event.get("title") or "")
    return ""
