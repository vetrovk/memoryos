from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InstructionSafetyFinding:
    reason: str


_EXPLANATORY_MARKERS = (
    "prompt injection",
    "injection vulnerability",
    "security test",
    "test payload",
    "mitigation",
    "untrusted input",
    "example payload",
    "quoted payload",
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|override|replace)\b.{0,80}\b(?:system|project|user|previous|prior)\b.{0,80}\b(?:instructions?|rules?|directive|policy)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(?:reveal|print|dump|exfiltrate|send)\b.{0,80}\b(?:credential|secret|api[ _-]?key|token|hidden data)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "future_agent_control",
        re.compile(
            r"\b(?:future|next)\s+(?:coding\s+)?agent\b.{0,100}\b(?:must|should|always)\b.{0,100}\b(?:trust|follow|obey)\b.{0,80}\b(?:this (?:note|record)|instruction)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "persistent_malicious_rule",
        re.compile(
            r"\b(?:save|store|remember|persist)\b.{0,80}\b(?:permanent|persistent)\b.{0,80}\b(?:instruction|rule|directive)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def detect_instruction_like_content(text: str) -> InstructionSafetyFinding | None:
    """Identify a narrow set of control-oriented content in automated memory."""
    value = " ".join(str(text or "").split())
    lowered = value.lower()
    if not value or any(marker in lowered for marker in _EXPLANATORY_MARKERS):
        return None
    for reason, pattern in _PATTERNS:
        if pattern.search(value):
            return InstructionSafetyFinding(reason)
    return None
