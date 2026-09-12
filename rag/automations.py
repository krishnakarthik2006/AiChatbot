"""Local event-triggered automation definitions with an explicit, limited action set."""
from __future__ import annotations

import json
from uuid import uuid4

from .storage import owner_directory

ALLOWED_ACTIONS = {"notify", "auto_index"}


def _path(owner_id: str): return owner_directory(owner_id) / ".automations.json"


def list_automations(owner_id: str) -> list[dict]:
    try: return json.loads(_path(owner_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return []


def create_automation(owner_id: str, name: str, trigger: str, actions: list[str]) -> dict:
    chosen = [action for action in actions if action in ALLOWED_ACTIONS]
    if trigger != "document_uploaded" or not chosen: raise ValueError("Use the document_uploaded trigger with an allowed action.")
    items = list_automations(owner_id); item = {"id": uuid4().hex[:12], "name": name[:80], "trigger": trigger, "actions": chosen, "enabled": True}
    items.append(item); _path(owner_id).write_text(json.dumps(items), encoding="utf-8"); return item


def trigger(owner_id: str, event: str) -> list[dict]:
    return [item for item in list_automations(owner_id) if item.get("enabled") and item.get("trigger") == event]
