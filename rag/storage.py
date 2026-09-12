"""Filesystem-backed document inventory for the local ai_chatbot deployment."""
from __future__ import annotations

import json
import base64
import math
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .documents import SUPPORTED_SUFFIXES

ENCRYPTED_PREFIX = b"ai_chatbot:fernet:v1:"


def _cipher():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(sha256(os.getenv("SECRET_KEY", "dev-secret-change-in-production").encode()).digest())
    return Fernet(key)


def owner_directory(owner_id: str) -> Path:
    safe_owner = re.sub(r"[^A-Za-z0-9_-]", "_", str(owner_id))
    directory = config.USER_DOCUMENTS_DIR / safe_owner
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_filename(filename: str) -> str:
    name = Path(filename or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not cleaned or Path(cleaned).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("Only PDF, Word, text, Markdown, HTML, JSON, and CSV files are supported.")
    return cleaned


def document_path(owner_id: str, filename: str) -> Path:
    return owner_directory(owner_id) / safe_filename(filename)


def write_document(owner_id: str, filename: str, content: bytes) -> Path:
    path = document_path(owner_id, filename)
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archive = owner_directory(owner_id) / ".versions" / path.name
        archive.mkdir(parents=True, exist_ok=True)
        # The archived bytes remain encrypted with the same account key.
        (archive / f"{stamp}.bin").write_bytes(path.read_bytes())
    path.write_bytes(ENCRYPTED_PREFIX + _cipher().encrypt(content))
    return path


def read_document_bytes(owner_id: str, filename: str) -> bytes:
    payload = document_path(owner_id, filename).read_bytes()
    return _cipher().decrypt(payload[len(ENCRYPTED_PREFIX):]) if payload.startswith(ENCRYPTED_PREFIX) else payload


def document_versions(owner_id: str, filename: str) -> list[dict]:
    """List immutable encrypted backup versions without exposing their content."""
    folder = owner_directory(owner_id) / ".versions" / safe_filename(filename)
    if not folder.exists():
        return []
    return [
        {"id": item.stem, "archived_at": datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc).isoformat(), "size": item.stat().st_size}
        for item in sorted(folder.glob("*.bin"), reverse=True)
    ]


@contextmanager
def materialized_documents(owner_id: str):
    """Provide an ephemeral plaintext directory for indexers; encrypted originals never change."""
    with tempfile.TemporaryDirectory(prefix="ai_chatbot_index_") as temp:
        directory = Path(temp)
        for item in list_documents(owner_id):
            (directory / item["name"]).write_bytes(read_document_bytes(owner_id, item["name"]))
        yield directory


def _retention_path(owner_id: str) -> Path:
    return owner_directory(owner_id) / ".retention.json"


def retention_rules(owner_id: str) -> dict[str, str]:
    try:
        return json.loads(_retention_path(owner_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def set_retention(owner_id: str, filename: str, expires_at: str | None) -> dict[str, str]:
    """Set or clear an ISO-8601 expiry. Files are only removed by an explicit cleanup."""
    filename = safe_filename(filename)
    rules = retention_rules(owner_id)
    if expires_at:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        rules[filename] = parsed.astimezone(timezone.utc).isoformat()
    else:
        rules.pop(filename, None)
    _retention_path(owner_id).write_text(json.dumps(rules, indent=2), encoding="utf-8")
    return rules


def cleanup_expired_documents(owner_id: str) -> list[str]:
    rules = retention_rules(owner_id)
    now = datetime.now(timezone.utc)
    removed: list[str] = []
    for filename, expires_at in list(rules.items()):
        try:
            expired = datetime.fromisoformat(expires_at).astimezone(timezone.utc) <= now
            path = document_path(owner_id, filename)
        except (ValueError, OSError):
            rules.pop(filename, None)
            continue
        if expired:
            if path.exists():
                path.unlink()
                removed.append(filename)
            rules.pop(filename, None)
    _retention_path(owner_id).write_text(json.dumps(rules, indent=2), encoding="utf-8")
    return removed


def index_state_path(owner_id: str) -> Path:
    return owner_directory(owner_id) / ".index-state.json"


def load_index_state(owner_id: str) -> dict:
    try:
        return json.loads(index_state_path(owner_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"indexed_at": None, "chunks": 0}


def save_index_state(owner_id: str, chunks: int) -> None:
    index_state_path(owner_id).write_text(
        json.dumps({"indexed_at": datetime.now(timezone.utc).isoformat(), "chunks": chunks}),
        encoding="utf-8",
    )


def list_documents(owner_id: str) -> list[dict]:
    state = load_index_state(owner_id)
    rules = retention_rules(owner_id)
    records = []
    for path in sorted(owner_directory(owner_id).iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        stat = path.stat()
        records.append({
            "name": path.name,
            "size": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "indexed_at": state.get("indexed_at"),
            "status": "indexed" if state.get("indexed_at") else "pending",
            "version": sha256(read_document_bytes(owner_id, path.name)).hexdigest()[:12],
            "expires_at": rules.get(path.name),
        })
    return records


def write_audit_event(owner_id: str, action: str, detail: str = "") -> None:
    """Append a compact local audit record without storing document content or prompts."""
    event = {
        "at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail[:160],
    }
    with (owner_directory(owner_id) / ".audit.jsonl").open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(event) + "\n")


def audit_events(owner_id: str, limit: int = 50) -> list[dict]:
    path = owner_directory(owner_id) / ".audit.jsonl"
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(row) for row in rows[-limit:]][::-1]
    except (OSError, json.JSONDecodeError):
        return []


def admin_document_overview() -> list[dict]:
    if not config.USER_DOCUMENTS_DIR.exists():
        return []
    return [
        {"account_id": path.name, "documents": list_documents(path.name), "events": audit_events(path.name, limit=10)}
        for path in config.USER_DOCUMENTS_DIR.iterdir() if path.is_dir()
    ]


def _append_jsonl(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as event_file:
        event_file.write(json.dumps(event) + "\n")


def record_metric(owner_id: str, confidence: float, latency_ms: int, sources: int, web_fallback: bool, query: str = "") -> None:
    _append_jsonl(owner_directory(owner_id) / ".metrics.jsonl", {
        "at": datetime.now(timezone.utc).isoformat(), "confidence": confidence,
        "latency_ms": latency_ms, "sources": sources, "web_fallback": web_fallback, "query": query[:160],
    })


def record_feedback(owner_id: str, message_id: str, helpful: bool, question: str, response: str) -> None:
    _append_jsonl(owner_directory(owner_id) / ".feedback.jsonl", {
        "at": datetime.now(timezone.utc).isoformat(), "message_id": message_id,
        "helpful": helpful, "question": question[:200], "response": response[:500],
    })


def _read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, json.JSONDecodeError):
        return []


def admin_metrics() -> dict:
    metrics, failed = [], []
    if not config.USER_DOCUMENTS_DIR.exists():
        return {"answers": 0, "average_latency_ms": 0, "average_confidence": 0, "helpful_rate": None, "failed_reviews": []}
    for directory in config.USER_DOCUMENTS_DIR.iterdir():
        if not directory.is_dir():
            continue
        metrics.extend(_read_jsonl(directory / ".metrics.jsonl"))
        failed.extend([{**item, "account_id": directory.name} for item in _read_jsonl(directory / ".feedback.jsonl") if not item.get("helpful")])
    return {
        "answers": len(metrics),
        "average_latency_ms": round(sum(item["latency_ms"] for item in metrics) / len(metrics)) if metrics else 0,
        "average_confidence": round(sum(item["confidence"] for item in metrics) / len(metrics), 3) if metrics else 0,
        "helpful_rate": None,
        "failed_reviews": failed[-30:][::-1],
        "weak_queries": [item.get("query", "") for item in metrics if item.get("confidence", 0) < config.RETRIEVAL_CONFIDENCE_THRESHOLD and item.get("query")][-30:][::-1],
    }


def _directory_size_bytes(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def admin_chroma_status() -> dict:
    """Collection counts and persisted corpus size across the Chroma stores."""
    collections, total_chunks = [], 0
    try:
        import chromadb
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        for collection in client.list_collections():
            count = collection.count()
            total_chunks += count
            collections.append({"name": collection.name, "chunks": count})
        collections.sort(key=lambda item: item["name"])
        return {
            "connected": True,
            "collections": collections,
            "total_chunks": total_chunks,
            "directory_size_bytes": _directory_size_bytes(config.CHROMA_DIR),
        }
    except Exception as exc:
        return {
            "connected": False,
            "error": str(exc),
            "collections": collections,
            "total_chunks": total_chunks,
            "directory_size_bytes": _directory_size_bytes(config.CHROMA_DIR),
        }


def admin_metrics_timeline(days: int = 14) -> list[dict]:
    """Per-UTC-day answer volume and average latency across all accounts."""
    totals: dict[str, dict] = {}
    if config.USER_DOCUMENTS_DIR.exists():
        for directory in config.USER_DOCUMENTS_DIR.iterdir():
            if not directory.is_dir():
                continue
            for item in _read_jsonl(directory / ".metrics.jsonl"):
                try:
                    day = datetime.fromisoformat(item["at"]).astimezone(timezone.utc).date().isoformat()
                except (KeyError, ValueError):
                    continue
                bucket = totals.setdefault(day, {"answers": 0, "latency": 0})
                bucket["answers"] += 1
                bucket["latency"] += int(item.get("latency_ms", 0))
    today = datetime.now(timezone.utc).date()
    timeline = []
    for offset in range(max(days, 1) - 1, -1, -1):
        date_label = (today - timedelta(days=offset)).isoformat()
        bucket = totals.get(date_label, {"answers": 0, "latency": 0})
        timeline.append({
            "date": date_label,
            "answers": bucket["answers"],
            "average_latency_ms": round(bucket["latency"] / bucket["answers"]) if bucket["answers"] else 0,
        })
    return timeline


def _storage_history() -> list[dict]:
    records = [] if not config.ADMIN_DATA_DIR.exists() else _read_jsonl(config.ADMIN_DATA_DIR / ".storage_history.jsonl")
    return [record for record in records if "at" in record]


def _storage_growth_mb() -> dict:
    """Snapshot user/chroma storage size and report growth since the last sample."""
    total = _directory_size_bytes(config.USER_DOCUMENTS_DIR) + _directory_size_bytes(config.CHROMA_DIR)
    total_mb = round(total / (1024 * 1024), 1)
    records = _storage_history()
    previous = records[-1].get("total_bytes") if records else None
    config.ADMIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _append_jsonl(config.ADMIN_DATA_DIR / ".storage_history.jsonl", {
        "at": datetime.now(timezone.utc).isoformat(), "total_bytes": total, "total_mb": total_mb,
    })
    if len(records) > 90:
        trimmed = records[-90:]
        (config.ADMIN_DATA_DIR / ".storage_history.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in trimmed), encoding="utf-8"
        )
    growth_mb = round((total - (previous or 0)) / (1024 * 1024), 1)
    return {"growth_mb": growth_mb, "total_mb": total_mb}


def admin_anomalies(days: int = 30) -> dict:
    """Flag daily request spikes and storage growth beyond configured thresholds."""
    anomalies: list[dict] = []
    timeline = admin_metrics_timeline(days=max(days, 7))
    active = [day for day in timeline if day["answers"] > 0]
    total = sum(day["answers"] for day in active)
    baseline = total / len(active) if active else 0
    for day in active:
        others_mean = (total - day["answers"]) / max(1, len(active) - 1) if len(active) > 1 else baseline
        threshold = max(math.ceil(2.5 * others_mean), 10)
        if baseline > 0 and day["answers"] >= threshold:
            anomalies.append({
                "type": "request_spike", "date": day["date"], "requests": day["answers"],
                "baseline": round(baseline, 1),
                "detail": f"{day['answers']} documents answers on {day['date']} vs ~{baseline:.0f}/day baseline",
            })
    growth = _storage_growth_mb()
    alert_mb = float(os.getenv("RAG_STORAGE_GROWTH_ALERT_MB", "200"))
    if growth["growth_mb"] >= alert_mb:
        anomalies.append({
            "type": "storage_growth", "growth_mb": growth["growth_mb"], "total_mb": growth["total_mb"],
            "detail": f"{growth['growth_mb']:.1f} MB added since the last admin check "
                      f"(total {growth['total_mb']:.1f} MB). Review uploaded documents.",
        })
    anomalies.sort(key=lambda item: item.get("date", "0"), reverse=True)
    return {"anomalies": anomalies, "checked_at": datetime.now(timezone.utc).isoformat()}
