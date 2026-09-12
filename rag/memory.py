"""User-editable long-term memory, kept separate from chat history."""
from __future__ import annotations

import json

from . import config
from .storage import owner_directory


def _path(owner_id: str):
    return owner_directory(owner_id) / ".memory.json"


def get_memory(owner_id: str) -> list[str]:
    try:
        value = json.loads(_path(owner_id).read_text(encoding="utf-8"))
        return [str(item) for item in value if str(item).strip()][:config.MEMORY_MAX_ITEMS]
    except (OSError, json.JSONDecodeError):
        return []


def set_memory(owner_id: str, items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()][:config.MEMORY_MAX_ITEMS]
    _path(owner_id).write_text(json.dumps(cleaned, ensure_ascii=False), encoding="utf-8")
    return cleaned
