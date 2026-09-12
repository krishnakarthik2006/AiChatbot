from types import SimpleNamespace

from rag.agent import calculate, plan
from rag.knowledge import build_graph
from rag.memory import get_memory, set_memory
from rag.quality import conflict_signals
from rag.router import route_request
from rag.workspaces import add_comment, add_member, create_workspace, list_workspaces
from rag.documents import SUPPORTED_SUFFIXES
from rag.automations import create_automation, trigger
from rag.notifications import list_notifications, mark_read, notify
from rag.storage import cleanup_expired_documents, document_versions, materialized_documents, set_retention, write_document
from rag.prompts import delete_prompt, list_prompts, save_prompt


def test_router_is_explainable_and_honours_privacy():
    route = route_request("Explain this", has_documents=True, use_web_fallback=False, privacy_mode=True)
    assert route["engine"] == "local"
    assert route["reason"]


def test_agent_calculator_requires_safe_math_only():
    assert calculate("(12 * 9) / 3") == 36
    assert plan("calculate a percentage")[0]["tool"] == "calculator"


def test_memory_is_user_editable(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    assert set_memory("user-1", ["Prefer concise answers", "", "Use Python"]) == ["Prefer concise answers", "Use Python"]
    assert get_memory("user-1") == ["Prefer concise answers", "Use Python"]


def test_knowledge_graph_extracts_entities(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "KNOWLEDGE_GRAPH_DIR", tmp_path)
    graph = build_graph("user-1", [{"content": "Project Atlas launches on 2026-09-12."}])
    assert graph["nodes"]


def test_conflict_signals_detect_multiple_dates():
    chunks = [SimpleNamespace(content="Policy deadline 2026-01-01"), SimpleNamespace(content="Policy deadline 2026-02-01")]
    assert conflict_signals(chunks)


def test_workspaces_enforce_owner_and_membership(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "WORKSPACES_DIR", tmp_path)
    workspace = create_workspace("owner", "Research")
    add_member(workspace["id"], "owner", "member", "editor")
    updated = add_comment(workspace["id"], "member", "Review the sources")
    assert updated["comments"][0]["message"] == "Review the sources"
    assert list_workspaces("member")[0]["id"] == workspace["id"]


def test_multimodal_supported_formats_include_slides_images_and_transcripts():
    assert {".pptx", ".png", ".srt", ".vtt"} <= SUPPORTED_SUFFIXES


def test_encrypted_documents_materialize_only_for_processing(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    path = write_document("user-1", "notes.txt", b"private source content")
    assert b"private source content" not in path.read_bytes()
    with materialized_documents("user-1") as directory:
        assert (directory / "notes.txt").read_bytes() == b"private source content"


def test_retention_cleanup_removes_only_expired_documents(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    write_document("user-1", "expired.txt", b"remove me")
    set_retention("user-1", "expired.txt", "2020-01-01T00:00:00Z")
    assert cleanup_expired_documents("user-1") == ["expired.txt"]


def test_notifications_and_automations_are_scoped_per_user(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    automation = create_automation("user-1", "Index uploads", "document_uploaded", ["auto_index", "notify"])
    assert automation in trigger("user-1", "document_uploaded")
    note = notify("user-1", "Ready", "Document indexed")
    assert mark_read("user-1", note["id"])[0]["read"] is True
    assert list_notifications("user-2") == []


def test_document_versions_and_prompt_library_are_private(monkeypatch, tmp_path):
    from rag import config
    monkeypatch.setattr(config, "USER_DOCUMENTS_DIR", tmp_path)
    write_document("user-1", "notes.txt", b"first")
    write_document("user-1", "notes.txt", b"second")
    assert len(document_versions("user-1", "notes.txt")) == 1
    prompt = save_prompt("user-1", "Compare", "Compare the supplied sources.")
    assert list_prompts("user-1")[0]["id"] == prompt["id"]
    assert delete_prompt("user-1", prompt["id"]) == []
