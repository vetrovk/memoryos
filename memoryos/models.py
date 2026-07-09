from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NoteInput:
    title: str
    type: str = "idea"
    project: str = ""
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    text: str = ""
    source: str = "manual"
    parent: str = ""
    related: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    extra_meta: dict[str, object] = field(default_factory=dict)


@dataclass
class TaskLearningInput:
    project: str
    goal: str
    actions: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = "agent"
    actor: str = "agent"
    status: str = "active"
    related: list[str] = field(default_factory=list)
    outcome: str = "completed"
    quality_score: int = 0


@dataclass
class SearchResult:
    id: str
    path: str
    title: str
    type: str
    project: str
    updated: str
    tags: list[str]
    snippet: str


@dataclass
class SessionLearningPreview:
    learning: TaskLearningInput
    cwd: str
    git_root: str = ""
    git_remote: str = ""
    git_status: str = ""
    git_diff_stat: str = ""
    last_commit: str = ""
    disposition: str = "permanent"
    reason: str = ""


@dataclass
class LearningSaveResult:
    disposition: str
    message: str
    path: str = ""
    quality_score: int = 0
    reason: str = ""
