from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import FOLDERS, database_path, log_path
from .util import now_text


SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    project TEXT,
    status TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created TEXT,
    updated TEXT,
    source TEXT,
    parent TEXT,
    related_json TEXT NOT NULL DEFAULT '[]',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    mtime REAL NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT,
    status TEXT,
    updated TEXT
);

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT,
    company TEXT,
    updated TEXT
);

CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT,
    project TEXT,
    updated TEXT
);

CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY,
    note_id TEXT NOT NULL,
    command TEXT NOT NULL,
    tool TEXT,
    created TEXT,
    FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
    tag TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY(note_id, tag),
    FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'related',
    created TEXT,
    FOREIGN KEY(source_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT PRIMARY KEY,
    note_id TEXT NOT NULL,
    FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    note_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local',
    reason TEXT,
    created TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
    note_id UNINDEXED,
    title,
    content,
    project,
    tags,
    type UNINDEXED,
    path UNINDEXED,
    updated UNINDEXED,
    tokenize = 'unicode61'
);
"""


def ensure_dirs(home: Path) -> None:
    for folder in FOLDERS:
        (home / folder).mkdir(parents=True, exist_ok=True)


def connect(home: Path) -> sqlite3.Connection:
    ensure_dirs(home)
    con = sqlite3.connect(database_path(home))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def log_error(home: Path, message: str) -> None:
    path = log_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_text()}] {message}\n")


def add_history(con: sqlite3.Connection, note_id: str | None, action: str, actor: str = "local", reason: str = "", payload: dict | None = None) -> None:
    con.execute(
        "INSERT INTO history(note_id, action, actor, reason, created, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (note_id, action, actor, reason, now_text(), json.dumps(payload or {}, ensure_ascii=False)),
    )
