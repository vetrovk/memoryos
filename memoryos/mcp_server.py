from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .api import Memory


DEFAULT_LIMIT = 10
DEFAULT_MAX_BYTES = 4096
MAX_LIMIT = 25
MAX_BYTES = 8192


class MemoryMCPService:
    """Bounded, read-only views over the existing MemoryOS Python API."""

    def __init__(self, home: str | Path | None = None) -> None:
        self.memory = Memory(home)

    def search_memory(self, query: str, project: str = "", cwd: str = "", limit: int = DEFAULT_LIMIT, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        project_name = self._project(project, cwd)
        results = self.memory.search_read_only(query, project=project_name, limit=self._limit(limit))
        payload = {
            "project": project_name,
            "query": query[:160],
            "results": [
                {"id": item.id, "title": item.title, "type": item.type, "project": item.project, "updated": item.updated, "tags": item.tags, "snippet": item.snippet}
                for item in results
            ],
        }
        return self._bounded(payload, max_bytes)

    def get_project_context(self, project: str = "", cwd: str = "", limit: int = DEFAULT_LIMIT, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        project_name = self._project(project, cwd)
        context = self.memory.session_context_read_only(project_name, limit=self._limit(limit), max_bytes=self._bytes(max_bytes))
        return self._bounded({"project": project_name, "context": context}, max_bytes)

    def open_memory(self, note_id: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        meta, body = self.memory.open_note_read_only(note_id)
        safe_meta = {key: meta.get(key) for key in ("id", "title", "type", "project", "status", "outcome", "tags", "created", "updated") if key in meta}
        return self._bounded({"note": safe_meta, "content": body}, max_bytes)

    def get_memory_stats(self, days: int | None = None, project: str = "") -> dict[str, Any]:
        return {"index": self.memory.memory_stats_read_only(), "usage": self.memory.usage_stats(days=days, project=project)}

    def _project(self, project: str, cwd: str) -> str:
        if project:
            return project
        if cwd:
            return self.memory.project_from_cwd(cwd)[1]
        raise ValueError("Provide project or cwd")

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(int(limit), MAX_LIMIT))

    @staticmethod
    def _bytes(max_bytes: int) -> int:
        return max(256, min(int(max_bytes), MAX_BYTES))

    def _bounded(self, payload: dict[str, Any], max_bytes: int) -> dict[str, Any]:
        budget = self._bytes(max_bytes)
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(encoded) <= budget:
            return payload
        text = json.dumps(payload, ensure_ascii=False)
        clipped = text.encode("utf-8")[: max(0, budget - 64)].decode("utf-8", errors="ignore")
        return {"truncated": True, "content": clipped}


def serve(home: str | Path | None = None) -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("MCP support is optional. Install it with: python -m pip install 'memoryos-local[mcp]'") from exc

    service = MemoryMCPService(home)
    server = FastMCP("MemoryOS")

    @server.tool()
    def search_memory(query: str, project: str = "", cwd: str = "", limit: int = DEFAULT_LIMIT, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        """Search local MemoryOS notes without modifying memory."""
        return service.search_memory(query, project, cwd, limit, max_bytes)

    @server.tool()
    def get_project_context(project: str = "", cwd: str = "", limit: int = DEFAULT_LIMIT, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        """Return bounded read-only project context."""
        return service.get_project_context(project, cwd, limit, max_bytes)

    @server.tool()
    def open_memory(note_id: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
        """Open one saved MemoryOS note by id without recording usage."""
        return service.open_memory(note_id, max_bytes)

    @server.tool()
    def get_memory_stats(days: int | None = None, project: str = "") -> dict[str, Any]:
        """Return local index and usage statistics without modifying data."""
        return service.get_memory_stats(days, project)

    server.run(transport="stdio")
