from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from .models import SearchResult
from .util import fts_query, short_snippet


class SearchProvider(ABC):
    @abstractmethod
    def search(
        self,
        query: str = "",
        project: str = "",
        tags: list[str] | None = None,
        note_type: str = "",
        limit: int = 10,
    ) -> list[SearchResult]:
        raise NotImplementedError


class SQLiteFTSSearchProvider(SearchProvider):
    def __init__(self, con: sqlite3.Connection, home: Path) -> None:
        self.con = con
        self.home = home

    def search(
        self,
        query: str = "",
        project: str = "",
        tags: list[str] | None = None,
        note_type: str = "",
        limit: int = 10,
    ) -> list[SearchResult]:
        params: list[object] = []
        where: list[str] = []
        join = ""
        order = "notes.updated DESC"
        select = "notes.*"
        if query.strip():
            match = fts_query(query)
            if not match:
                return []
            join = "JOIN fts_index ON fts_index.note_id = notes.id"
            where.append("fts_index MATCH ?")
            params.append(match)
            select = "notes.*, bm25(fts_index) AS rank"
            order = "rank ASC"
        if project:
            where.append("lower(notes.project) = lower(?)")
            params.append(project)
        if note_type:
            where.append("notes.type = ?")
            params.append(note_type)
        for tag in tags or []:
            where.append("notes.id IN (SELECT note_id FROM note_tags WHERE tag = ?)")
            params.append(tag)
        sql = f"SELECT {select} FROM notes {join}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order} LIMIT ?"
        params.append(limit)
        rows = self.con.execute(sql, params).fetchall()
        return [
            SearchResult(
                id=row["id"],
                path=str(self.home / row["path"]),
                title=row["title"],
                type=row["type"],
                project=row["project"] or "",
                updated=row["updated"] or "",
                tags=json.loads(row["tags_json"] or "[]"),
                snippet=short_snippet(row["content"], query),
            )
            for row in rows
        ]
