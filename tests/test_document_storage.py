from rag import config
from rag.storage import admin_metrics, admin_metrics_timeline, audit_events, document_path, record_feedback, record_metric, safe_filename, write_audit_event


def test_document_filename_validation_rejects_path_traversal_and_unknown_types():
    assert safe_filename("../notes.pdf") == "notes.pdf"
    try:
        safe_filename("malware.exe")
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported file types must be rejected")


def test_document_paths_are_scoped_to_a_user_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    path = document_path("account-12", "handbook.txt")
    assert path.parent.name == "account-12"
    assert path.name == "handbook.txt"


def test_audit_log_does_not_store_document_content(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    write_audit_event("account-1", "document_uploaded", "handbook.pdf")
    assert audit_events("account-1")[0]["detail"] == "handbook.pdf"


def test_metrics_and_unhelpful_feedback_are_available_for_review(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    record_metric("account-1", 0.7, 120, 2, False)
    record_feedback("account-1", "message-1", False, "Question", "Answer")
    summary = admin_metrics()
    assert summary["answers"] == 1
    assert summary["failed_reviews"][0]["message_id"] == "message-1"


def test_metrics_timeline_aggregates_by_utc_day(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    record_metric("account-1", 0.7, 120, 2, False)
    timeline = admin_metrics_timeline(days=3)
    assert len(timeline) == 3
    today = timeline[-1]
    assert today["answers"] == 1
    assert today["average_latency_ms"] == 120
    assert all(item["answers"] == 0 for item in timeline[:-1])
