import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rag import config, storage


def _isolate(tmp_path):
    root = Path(tmp_path)
    config.USER_DOCUMENTS_DIR = root / "user_documents"
    config.CHROMA_DIR = root / "chroma"
    config.ADMIN_DATA_DIR = root / "admin_data"
    config.USER_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    return root


def test_admin_anomalies_flags_request_spike(tmp_path):
    _isolate(tmp_path)
    user = config.USER_DOCUMENTS_DIR / "acc1"
    user.mkdir()
    today = datetime.now(timezone.utc).date()
    for offset, count in [(2, 12), (3, 9), (4, 13), (5, 10), (1, 95)]:
        day = (today - timedelta(days=offset)).isoformat()
        for _ in range(count):
            storage._append_jsonl(user / ".metrics.jsonl", {"at": day, "confidence": 0.9, "latency_ms": 100, "sources": 2})

    anomalies = storage.admin_anomalies(days=14)["anomalies"]
    spike = next((item for item in anomalies if item["type"] == "request_spike"), None)
    assert spike is not None
    assert spike["requests"] == 95
    assert "95" in spike["detail"]


def test_admin_anomalies_reports_storage_growth(tmp_path):
    _isolate(tmp_path)
    storage.admin_anomalies(days=7)  # seeds the baseline sample
    big = config.USER_DOCUMENTS_DIR / "acc1"
    big.mkdir(parents=True, exist_ok=True)
    with open(big / "big.bin", "wb") as handle:
        handle.write(os.urandom(300 * 1024 * 1024))

    anomalies = storage.admin_anomalies(days=7)["anomalies"]
    growth = next((item for item in anomalies if item["type"] == "storage_growth"), None)
    assert growth is not None
    assert growth["growth_mb"] >= 300


def test_admin_anomalies_empty_when_quiet(tmp_path):
    _isolate(tmp_path)
    result = storage.admin_anomalies(days=7)
    assert result["anomalies"] == []
    assert "checked_at" in result