from __future__ import annotations

import os
import json
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
    "oss_candidate": "70_decisions",
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
        "oss_candidate",
        "project_note",
    }
)


def memory_home(home: str | Path | None = None) -> Path:
    if home:
        return Path(home).expanduser().resolve()
    return Path(os.environ.get("MEMORY_HOME", "~/Memory")).expanduser().resolve()


def database_path(home: Path) -> Path:
    return home / "_system" / "database" / "memory.sqlite3"


def log_path(home: Path) -> Path:
    return home / "_system" / "logs" / "memory.log"


DEFAULT_CURATOR_CONFIG = {
    "ignored_path_segments": [
        ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt",
        ".cache", "cache", "tmp", "temp", ".tmp", ".venv", "venv",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "coverage", "htmlcov",
    ],
    "ignored_file_names": [".DS_Store", ".coverage"],
    "ignored_suffixes": [".pyc", ".log"],
    "ignored_name_suffixes": [".min.js", ".min.css", ".bundle.js", ".chunk.js"],
    "near_duplicate_window_hours": 24,
    "near_duplicate_similarity": 0.8,
}

DEFAULT_PENDING_IMPORT_CONFIG = {
    "paths": ["~/Documents"],
}


def curator_config_path(home: Path) -> Path:
    return home / "_system" / "config" / "curator.json"


def load_curator_config(home: Path) -> dict:
    config = {key: list(value) if isinstance(value, list) else value for key, value in DEFAULT_CURATOR_CONFIG.items()}
    path = curator_config_path(home)
    if not path.exists():
        return config
    try:
        custom = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    if not isinstance(custom, dict):
        return config
    for key in config:
        if key in custom and isinstance(custom[key], type(config[key])):
            config[key] = custom[key]
    return config


def pending_import_config_path(home: Path) -> Path:
    return home / "_system" / "config" / "pending_import.json"


def pending_import_state_path(home: Path) -> Path:
    return home / "_system" / "cache" / "pending_imports.json"


def load_pending_import_config(home: Path) -> dict:
    config = {"paths": list(DEFAULT_PENDING_IMPORT_CONFIG["paths"])}
    path = pending_import_config_path(home)
    if not path.exists():
        return config
    try:
        custom = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    if isinstance(custom, dict) and isinstance(custom.get("paths"), list):
        config["paths"] = [str(item) for item in custom["paths"] if str(item).strip()]
    return config
