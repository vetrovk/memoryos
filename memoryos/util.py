from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def date_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def uuid_text() -> str:
    return str(uuid.uuid4())


def slugify(value: str, fallback: str = "note") -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def split_tags(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = re.split(r"[,;]", value)
    else:
        raw = list(value)
    return sorted({str(item).strip() for item in raw if str(item).strip()})


def frontmatter_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
    return json.dumps(value or "", ensure_ascii=False)


def build_markdown(meta: dict[str, object], body: str) -> str:
    keys = ["id", "title", "type", "project", "status", "tags", "created", "updated", "source", "parent", "related", "aliases"]
    keys.extend(key for key in meta if key not in keys)
    lines = ["---"]
    for key in keys:
        lines.append(f"{key}: {frontmatter_value(meta.get(key, [] if key in {'tags', 'related', 'aliases'} else ''))}")
    lines.extend(["---", "", body.rstrip(), ""])
    return "\n".join(lines)


def parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    return value


def read_markdown(path: Path) -> tuple[dict[str, object], str]:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, object] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            for line in raw[4:end].splitlines():
                if ":" not in line or line.strip().startswith("#"):
                    continue
                key, value = line.split(":", 1)
                meta[key.strip()] = parse_scalar(value)
            body = raw[end + 5 :]
    return meta, body.strip()


def short_snippet(content: str, query: str = "", size: int = 180) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return ""
    terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    start = 0
    lower = compact.lower()
    for term in terms:
        idx = lower.find(term.lower())
        if idx != -1:
            start = max(0, idx - size // 3)
            break
    snippet = compact[start : start + size]
    if start:
        snippet = "..." + snippet
    if start + size < len(compact):
        snippet += "..."
    return snippet


def fts_query(text: str) -> str:
    terms = re.findall(r"[\w-]+", text, flags=re.UNICODE)
    return " OR ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms)
