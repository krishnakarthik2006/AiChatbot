"""Small per-user prompt library for reusable grounded queries."""
from __future__ import annotations

import json
from uuid import uuid4

from .storage import owner_directory


def _path(owner_id: str):
    return owner_directory(owner_id) / ".prompt-library.json"


def list_prompts(owner_id: str) -> list[dict]:
    try:
        return json.loads(_path(owner_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_prompt(owner_id: str, title: str, text: str) -> dict:
    item = {"id": uuid4().hex[:12], "title": title.strip()[:80], "text": text.strip()[:1000]}
    if not item["title"] or not item["text"]:
        raise ValueError("A prompt title and text are required.")
    items = list_prompts(owner_id) + [item]
    _path(owner_id).write_text(json.dumps(items[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def delete_prompt(owner_id: str, prompt_id: str) -> list[dict]:
    items = [item for item in list_prompts(owner_id) if item.get("id") != prompt_id]
    _path(owner_id).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return items
