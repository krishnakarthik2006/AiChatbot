"""Per-user, in-app notification inbox used by documents, automations, and workspaces."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from .storage import owner_directory


def _path(owner_id: str): return owner_directory(owner_id) / ".notifications.json"


def list_notifications(owner_id: str) -> list[dict]:
    try: return json.loads(_path(owner_id).read_text(encoding="utf-8"))[-50:][::-1]
    except (OSError, json.JSONDecodeError): return []


def notify(owner_id: str, title: str, detail: str = "") -> dict:
    items = list_notifications(owner_id)[::-1]
    item = {"id": uuid4().hex[:12], "title": title[:100], "detail": detail[:240], "read": False, "at": datetime.now(timezone.utc).isoformat()}
    items.append(item); _path(owner_id).write_text(json.dumps(items[-50:]), encoding="utf-8"); return item


def mark_read(owner_id: str, notification_id: str) -> list[dict]:
    items = list_notifications(owner_id)[::-1]
    for item in items:
        if item["id"] == notification_id: item["read"] = True
    _path(owner_id).write_text(json.dumps(items), encoding="utf-8"); return items[::-1]
