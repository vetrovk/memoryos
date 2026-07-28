from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CredentialFinding:
    kind: str


class CredentialDetectedError(ValueError):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(
            f"Credential detected ({kind}); saving blocked. "
            "Use --allow-credentials only for an intentional local save."
        )


_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("openai_api_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
)
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|api[_-]?key|access[_-]?token|secret)\b\s*[:=]\s*"
    r"(\"[^\"]+\"|'[^']+'|[^\s,;]+)"
)
_PLACEHOLDER = re.compile(
    r"(?i)^(?:<[^>]+>|\$\{[^}]+\}|\[[^]]+\]|your[_-].+|replace[_-].+|example|placeholder)$"
)


def detect_credential(text: str) -> CredentialFinding | None:
    value = str(text or "")
    for kind, pattern in _PATTERNS:
        if pattern.search(value):
            return CredentialFinding(kind)
    for match in _ASSIGNMENT.finditer(value):
        assigned = match.group(2).strip("\"'")
        if assigned and not _PLACEHOLDER.fullmatch(assigned):
            return CredentialFinding("explicit_assignment")
    return None


def guard_credentials(values: Iterable[object], allow_credentials: bool = False) -> None:
    if allow_credentials:
        return
    try:
        for value in values:
            finding = detect_credential(str(value or ""))
            if finding:
                raise CredentialDetectedError(finding.kind)
    except CredentialDetectedError:
        raise
    except Exception:
        raise CredentialDetectedError("scan_failed") from None
