"""Small, deterministic safety checks used before retrieval and generation."""
from __future__ import annotations

import re

INJECTION_PATTERNS = (
    r"ignore (all |any |the )?(previous|above|earlier) instructions",
    r"disregard (all |any |the )?(previous|above|earlier) instructions",
    r"reveal (the )?(system prompt|hidden prompt)",
    r"you are now",
    r"jailbreak",
)


def contains_prompt_injection(text: str) -> bool:
    """Return true for common attempts to override the assistant's instructions."""
    normalised = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalised) for pattern in INJECTION_PATTERNS)


def detect_language_hint(text: str) -> str:
    """Give the model a useful language hint without depending on an external service."""
    value = text or ""
    if re.search(r"[\u0900-\u097f]", value):
        return "Hindi"
    if re.search(r"[\u0b80-\u0bff]", value):
        return "Tamil"
    if re.search(r"[\u0c00-\u0c7f]", value):
        return "Telugu"
    return "the same language as the question"

