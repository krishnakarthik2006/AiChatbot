"""Atomic JSON persistence for local application data.

ChromaDB remains the independent vector store for RAG embeddings. This file stores only
accounts, authenticated chat sessions, message history, and optional training metadata.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from werkzeug.security import generate_password_hash
from backend.models import Account

_LOCK = Lock()


def _path(): return Path(__file__).resolve().parent / "local_store.json"
def _empty(): return {"accounts": [], "sessions": [], "conversations": [], "intents": [], "model_metadata": []}
def _load():
    try: return {**_empty(), **json.loads(_path().read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError): return _empty()
def _save(data):
    path = _path(); temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path)
def _row(items, key, value): return next((item for item in items if str(item.get(key)) == str(value)), None)
def _object(row): return SimpleNamespace(**row) if row else None
def _account(row): return Account(**row) if row else None
def _next(items): return max((item["id"] for item in items), default=0) + 1
def _now(): return datetime.now(timezone.utc).isoformat()


def init_db(app=None):
    with _LOCK:
        if not _path().exists(): _save(_empty())


def create_account(email, password, display_name=None):
    with _LOCK:
        data = _load()
        if _row(data["accounts"], "email", email): return None
        row = {"id": _next(data["accounts"]), "email": email, "password_hash": generate_password_hash(password), "display_name": display_name, "created_at": _now()}
        data["accounts"].append(row); _save(data); return _account(row)


def get_account_by_email(email): return _account(_row(_load()["accounts"], "email", email))
def get_account_by_id(account_id): return _account(_row(_load()["accounts"], "id", account_id))


def create_user_session(session_id, account_id=None):
    with _LOCK:
        data = _load(); row = {"id": _next(data["sessions"]), "session_id": session_id, "account_id": account_id, "created_at": _now()}
        data["sessions"].append(row); _save(data); return _object(row)


def get_user_by_session_id(session_id): return _object(_row(_load()["sessions"], "session_id", session_id))
def get_user_for_account(session_id, account_id):
    user = get_user_by_session_id(session_id)
    return user if user and str(user.account_id) == str(account_id) else None


def save_conversation(user_id, user_message, bot_response, intent, confidence, engine, model):
    with _LOCK:
        data = _load(); row = {"id": _next(data["conversations"]), "user_id": user_id, "user_message": user_message, "bot_response": bot_response, "intent": intent, "confidence": confidence, "engine": engine, "model": model, "timestamp": _now()}
        data["conversations"].append(row); _save(data); return _object(row)


def get_conversation_history(user_id, limit=28):
    return [_object(row) for row in [item for item in _load()["conversations"] if str(item["user_id"]) == str(user_id)][-limit:]]


def clear_user_session(session_id, account_id=None):
    with _LOCK:
        data = _load(); user = _row(data["sessions"], "session_id", session_id)
        if not user or (account_id is not None and str(user["account_id"]) != str(account_id)): return False
        data["sessions"] = [item for item in data["sessions"] if item["session_id"] != session_id]
        data["conversations"] = [item for item in data["conversations"] if item["user_id"] != user["id"]]
        _save(data); return True


def save_intent(tag, patterns, responses):
    with _LOCK:
        data = _load(); data["intents"] = [item for item in data["intents"] if item["tag"] != tag]
        row = {"tag": tag, "patterns": patterns, "responses": responses}; data["intents"].append(row); _save(data); return _object(row)
def get_all_intents(): return _load()["intents"]
def save_model_metadata(model_name, version, intents_count, training_samples, accuracy):
    with _LOCK:
        data = _load(); row = {"model_name": model_name, "version": version, "intents_count": intents_count, "training_samples": training_samples, "accuracy": accuracy, "trained_at": _now()}
        data["model_metadata"].append(row); _save(data); return _object(row)
def get_model_metadata(model_name):
    rows = [item for item in _load()["model_metadata"] if item["model_name"] == model_name]
    return _object(rows[-1]) if rows else None
