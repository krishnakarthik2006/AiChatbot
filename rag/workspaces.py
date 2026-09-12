"""Local shared-workspace metadata with explicit member and role records."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from . import config


def _path():
    config.WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    return config.WORKSPACES_DIR / "workspaces.json"


def _load() -> list[dict]:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _save(workspaces: list[dict]) -> None:
    _path().write_text(json.dumps(workspaces, ensure_ascii=False, indent=2), encoding="utf-8")


def list_workspaces(member_id: str) -> list[dict]:
    return [workspace for workspace in _load() if member_id in workspace["members"]]


def create_workspace(owner_id: str, name: str) -> dict:
    workspace = {"id": uuid4().hex[:12], "name": name.strip()[:80], "owner_id": owner_id, "members": {owner_id: "owner"}, "documents": [], "comments": [], "events": [], "presence": {}, "created_at": datetime.now(timezone.utc).isoformat()}
    workspaces = _load(); workspaces.append(workspace); _save(workspaces)
    return workspace


def add_member(workspace_id: str, actor_id: str, member_id: str, role: str) -> dict:
    workspaces = _load()
    for workspace in workspaces:
        if workspace["id"] == workspace_id:
            if workspace["members"].get(actor_id) != "owner":
                raise PermissionError("Only the workspace owner can add members.")
            workspace["members"][member_id] = role if role in {"viewer", "editor"} else "viewer"
            _event(workspace, actor_id, "member_invited", member_id)
            _save(workspaces); return workspace
    raise LookupError("Workspace not found.")


def add_comment(workspace_id: str, member_id: str, message: str) -> dict:
    workspaces = _load()
    for workspace in workspaces:
        if workspace["id"] == workspace_id:
            if member_id not in workspace["members"]:
                raise PermissionError("You are not a workspace member.")
            workspace["comments"].append({"author_id": member_id, "message": message[:500], "at": datetime.now(timezone.utc).isoformat()})
            _event(workspace, member_id, "comment_added", message[:80])
            _save(workspaces); return workspace
    raise LookupError("Workspace not found.")


def _event(workspace: dict, actor_id: str, action: str, detail: str = "") -> None:
    workspace.setdefault("events", []).append({"at": datetime.now(timezone.utc).isoformat(), "actor_id": actor_id, "action": action, "detail": detail})
    workspace["events"] = workspace["events"][-100:]


def _workspace(workspaces: list[dict], workspace_id: str) -> dict:
    for workspace in workspaces:
        if workspace["id"] == workspace_id:
            workspace.setdefault("documents", []); workspace.setdefault("events", []); workspace.setdefault("presence", {})
            return workspace
    raise LookupError("Workspace not found.")


def attach_document(workspace_id: str, actor_id: str, owner_id: str, filename: str) -> dict:
    workspaces = _load(); workspace = _workspace(workspaces, workspace_id)
    if workspace["members"].get(actor_id) not in {"owner", "editor"}:
        raise PermissionError("Only workspace owners and editors can share documents.")
    reference = {"owner_id": owner_id, "filename": filename}
    if reference not in workspace["documents"]:
        workspace["documents"].append(reference); _event(workspace, actor_id, "document_shared", filename)
    _save(workspaces); return workspace


def workspace_for_member(workspace_id: str, member_id: str) -> dict:
    workspace = _workspace(_load(), workspace_id)
    if member_id not in workspace["members"]:
        raise PermissionError("You are not a workspace member.")
    return workspace


def update_presence(workspace_id: str, member_id: str) -> dict:
    workspaces = _load(); workspace = _workspace(workspaces, workspace_id)
    if member_id not in workspace["members"]:
        raise PermissionError("You are not a workspace member.")
    workspace["presence"][member_id] = datetime.now(timezone.utc).isoformat(); _save(workspaces)
    return workspace
