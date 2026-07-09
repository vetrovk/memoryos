from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BasePlugin(ABC):
    """Minimal plugin interface for future importers and automations."""

    name = "base"

    def __init__(self, memory: Any) -> None:
        self.memory = memory

    @abstractmethod
    def run(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class FilesystemPlugin(BasePlugin):
    name = "filesystem"

    def run(self, path: str, project: str = "", **_: Any) -> dict[str, Any]:
        imported = self.memory.import_path(Path(path), project=project)
        return {"imported": imported}
