from __future__ import annotations

import os
from pathlib import Path


FOLDERS = [
    "00_inbox",
    "10_projects",
    "20_people",
    "30_company",
    "40_health",
    "50_ai",
    "60_guides",
    "70_decisions",
    "80_errors",
    "90_archive",
    "_system",
    "_system/database",
    "_system/config",
    "_system/logs",
    "_system/exports",
    "_system/plugins",
    "_system/scripts",
    "_system/cache",
    "_system/launchd",
    "_system/drafts",
]

TYPE_FOLDERS = {
    "project": "10_projects",
    "project_note": "10_projects",
    "person": "20_people",
    "company": "30_company",
    "health_note": "40_health",
    "health": "40_health",
    "prompt": "50_ai",
    "session": "50_ai",
    "guide": "60_guides",
    "command": "60_guides",
    "decision": "70_decisions",
    "error": "80_errors",
    "architecture": "10_projects",
    "repository": "10_projects",
    "github_pr_learning": "70_decisions",
    "idea": "00_inbox",
}

OBJECT_TYPES = sorted(
    {
        "project",
        "person",
        "company",
        "guide",
        "decision",
        "error",
        "command",
        "session",
        "prompt",
        "idea",
        "health_note",
        "architecture",
        "repository",
        "github_pr_learning",
        "project_note",
    }
)


def memory_home(home: str | Path | None = None) -> Path:
    if home:
        return Path(home).expanduser().resolve()
    return Path(os.environ.get("MEMORY_HOME", "~/Memory")).expanduser().resolve()


def database_path(home: Path) -> Path:
    return home / "_system" / "database" / "memory.sqlite3"


def legacy_database_path(home: Path) -> Path:
    return home / "_system" / "memory.sqlite3"


def log_path(home: Path) -> Path:
    return home / "_system" / "logs" / "memory.log"
