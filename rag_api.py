"""FastAPI entrypoint for the ai_chatbot RAG service.

Run with: uvicorn rag_api:app --reload --port 8000
"""
from __future__ import annotations

import json
import tempfile
from time import perf_counter
from typing import List, Optional
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.service import RAGService
from rag.auth import current_identity, enforce_rate_limit, require_admin
from rag import config
from rag.storage import (admin_document_overview, admin_metrics_timeline, audit_events, document_path, list_documents,
                         owner_directory, safe_filename, save_index_state, write_audit_event,
                         record_feedback, record_metric, admin_metrics, materialized_documents,
                         read_document_bytes, write_document, cleanup_expired_documents,
                         retention_rules, set_retention, document_versions)
from rag.evaluation import (EVALUATION_CASES, evaluation_history, record_evaluation,
                            run_guard_evaluation, run_retrieval_evaluation)
from rag.agent import analyze_document, calculate, compare_documents, plan
from rag.knowledge import get_graph
from rag.memory import get_memory, set_memory
from rag.workspaces import (add_comment, add_member, attach_document, create_workspace, list_workspaces,
                            update_presence, workspace_for_member)
from rag.quality import source_quality
from rag.notifications import list_notifications, mark_read, notify
from rag.automations import create_automation, list_automations, trigger
from rag.prompts import delete_prompt, list_prompts, save_prompt

app = FastAPI(title="ai_chatbot RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = RAGService()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    top_k: Optional[int] = Field(default=None, ge=1, le=10)
    history: List[dict] = Field(default_factory=list, max_length=8)
    language: Optional[str] = Field(default=None, max_length=60)
    use_web_fallback: bool = False
    privacy_mode: bool = False
    workspace_id: Optional[str] = Field(default=None, max_length=64)


class MemoryRequest(BaseModel):
    items: List[str] = Field(default_factory=list, max_length=40)


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    expression: Optional[str] = Field(default=None, max_length=120)
    left_document: Optional[str] = Field(default=None, max_length=255)
    right_document: Optional[str] = Field(default=None, max_length=255)


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MemberRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    role: str = Field(default="viewer", max_length=10)


class CommentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class AutomationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    trigger: str = Field(default="document_uploaded")
    actions: List[str] = Field(default_factory=lambda: ["notify"])


class RetentionRequest(BaseModel):
    expires_at: Optional[str] = Field(default=None, max_length=40)


class PromptRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)


class SourceExplorerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    workspace_id: Optional[str] = Field(default=None, max_length=64)


class FeedbackRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=100)
    helpful: bool
    question: str = Field(default="", max_length=200)
    response: str = Field(default="", max_length=500)


def owner_id(identity: dict) -> str:
    return str(identity["account_id"])


def workspace_directory(workspace: dict):
    """Build an ephemeral shared-document index from references the member is allowed to see."""
    temp = tempfile.TemporaryDirectory(prefix="ai_chatbot_workspace_")
    directory = Path(temp.name)
    for reference in workspace.get("documents", []):
        target = directory / f"{reference['owner_id']}_{reference['filename']}"
        target.write_bytes(read_document_bytes(reference["owner_id"], reference["filename"]))
    return temp, directory


def permitted_namespace(workspace_id: str | None, identity: dict) -> str:
    if not workspace_id:
        return owner_id(identity)
    try:
        return f"workspace_{workspace_for_member(workspace_id, owner_id(identity))['id']}"
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="You are not a workspace member.") from exc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "rag": service.status()}


@app.get("/api/documents")
def documents(identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    removed = cleanup_expired_documents(owner)
    if removed:
        write_audit_event(owner, "retention_cleanup", ", ".join(removed))
    return {"documents": list_documents(owner), "expired_removed": removed}


@app.get("/api/documents/retention")
def get_retention(identity: dict = Depends(current_identity)) -> dict:
    return {"rules": retention_rules(owner_id(identity))}


@app.put("/api/documents/{filename}/retention")
def update_retention(filename: str, payload: RetentionRequest, identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    try:
        if not document_path(owner, filename).exists():
            raise HTTPException(status_code=404, detail="Document not found.")
        rules = set_retention(owner, filename, payload.expires_at)
        write_audit_event(owner, "retention_updated", safe_filename(filename))
        return {"rules": rules}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Use a valid ISO-8601 expiration date.") from exc


@app.get("/api/documents/{filename}/versions")
def versions(filename: str, identity: dict = Depends(current_identity)) -> dict:
    try:
        return {"versions": document_versions(owner_id(identity), filename)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/prompts")
def prompts(identity: dict = Depends(current_identity)) -> dict:
    return {"prompts": list_prompts(owner_id(identity))}


@app.post("/api/prompts")
def create_prompt(payload: PromptRequest, identity: dict = Depends(current_identity)) -> dict:
    try:
        return save_prompt(owner_id(identity), payload.title, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/prompts/{prompt_id}")
def remove_prompt(prompt_id: str, identity: dict = Depends(current_identity)) -> dict:
    return {"prompts": delete_prompt(owner_id(identity), prompt_id)}


@app.post("/api/source-explorer")
def source_explorer(payload: SourceExplorerRequest, identity: dict = Depends(current_identity)) -> dict:
    namespace = permitted_namespace(payload.workspace_id, identity)
    try:
        chunks = service.retrieve(payload.query, top_k=5, namespace=namespace)
        return {"chunks": [{"source": chunk.source, "chunk_id": chunk.chunk_id, "score": round(chunk.score or 0, 3), "excerpt": chunk.content[:500]} for chunk in chunks]}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not search this index: {exc}") from exc


@app.get("/api/memory")
def memory(identity: dict = Depends(current_identity)) -> dict:
    return {"items": get_memory(owner_id(identity))}


@app.put("/api/memory")
def update_memory(payload: MemoryRequest, identity: dict = Depends(current_identity)) -> dict:
    items = set_memory(owner_id(identity), payload.items)
    write_audit_event(owner_id(identity), "memory_updated", f"{len(items)} items")
    return {"items": items}


@app.get("/api/knowledge-graph")
def knowledge_graph(identity: dict = Depends(current_identity)) -> dict:
    return get_graph(owner_id(identity))


@app.get("/api/source-quality")
def quality(identity: dict = Depends(current_identity)) -> dict:
    return source_quality(owner_id(identity))


@app.post("/api/agent/plan")
def agent_plan(payload: AgentRequest, identity: dict = Depends(current_identity)) -> dict:
    return {"steps": plan(payload.question), "requires_approval": bool(payload.expression)}


@app.post("/api/agent/execute")
def agent_execute(payload: AgentRequest, identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    try:
        with materialized_documents(owner) as directory:
            if payload.left_document and payload.right_document:
                return {"tool": "document_compare", **compare_documents(directory / safe_filename(payload.left_document), directory / safe_filename(payload.right_document))}
            if payload.left_document:
                return {"tool": "document_analysis", **analyze_document(directory / safe_filename(payload.left_document))}
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload.expression:
        raise HTTPException(status_code=400, detail="An approved numeric expression is required for execution.")
    try:
        result = calculate(payload.expression)
    except (SyntaxError, ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit_event(owner_id(identity), "agent_calculator", "approved calculation")
    return {"tool": "calculator", "expression": payload.expression, "result": result}


@app.post("/api/agent/report")
def agent_report(payload: AgentRequest, identity: dict = Depends(current_identity)) -> dict:
    """Generate a cited report using only the caller's grounded document index."""
    report_question = f"Create a structured report with an executive summary, key findings, and source citations about: {payload.question}"
    return service.answer(report_question, namespace=owner_id(identity), memory=get_memory(owner_id(identity)))


@app.get("/api/workspaces")
def workspaces(identity: dict = Depends(current_identity)) -> dict:
    return {"workspaces": list_workspaces(owner_id(identity))}


@app.post("/api/workspaces")
def new_workspace(payload: WorkspaceRequest, identity: dict = Depends(current_identity)) -> dict:
    return create_workspace(owner_id(identity), payload.name)


@app.post("/api/workspaces/{workspace_id}/members")
def workspace_member(workspace_id: str, payload: MemberRequest, identity: dict = Depends(current_identity)) -> dict:
    try:
        result = add_member(workspace_id, owner_id(identity), payload.account_id, payload.role)
        notify(payload.account_id, "Workspace invitation", f"You were added to {result['name']} as {payload.role}.")
        return result
    except (PermissionError, LookupError) as exc:
        raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 404, detail=str(exc)) from exc


@app.post("/api/workspaces/{workspace_id}/comments")
def workspace_comment(workspace_id: str, payload: CommentRequest, identity: dict = Depends(current_identity)) -> dict:
    try:
        return add_comment(workspace_id, owner_id(identity), payload.message)
    except (PermissionError, LookupError) as exc:
        raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 404, detail=str(exc)) from exc


@app.post("/api/workspaces/{workspace_id}/documents/{filename}")
def share_document(workspace_id: str, filename: str, identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    try:
        if not document_path(owner, filename).exists(): raise HTTPException(status_code=404, detail="Document not found.")
        workspace = attach_document(workspace_id, owner, owner, safe_filename(filename))
        temp, directory = workspace_directory(workspace)
        try: service.ingest_directory(directory, namespace=f"workspace_{workspace_id}")
        finally: temp.cleanup()
        for member in workspace["members"]:
            if member != owner: notify(member, "Shared document updated", f"{filename} is available in {workspace['name']}.")
        return workspace
    except (PermissionError, LookupError, ValueError) as exc:
        raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 404, detail=str(exc)) from exc


@app.get("/api/workspaces/{workspace_id}/events")
def workspace_events(workspace_id: str, identity: dict = Depends(current_identity)) -> dict:
    try:
        workspace = update_presence(workspace_id, owner_id(identity))
        return {"events": workspace.get("events", [])[-50:], "presence": workspace.get("presence", {}), "documents": workspace.get("documents", [])}
    except (PermissionError, LookupError) as exc:
        raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 404, detail=str(exc)) from exc


@app.get("/api/notifications")
def notifications(identity: dict = Depends(current_identity)) -> dict:
    return {"notifications": list_notifications(owner_id(identity))}


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, identity: dict = Depends(current_identity)) -> dict:
    return {"notifications": mark_read(owner_id(identity), notification_id)}


@app.get("/api/automations")
def automations(identity: dict = Depends(current_identity)) -> dict:
    return {"automations": list_automations(owner_id(identity))}


@app.post("/api/automations")
def automation(payload: AutomationRequest, identity: dict = Depends(current_identity)) -> dict:
    try: return create_automation(owner_id(identity), payload.name, payload.trigger, payload.actions)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...), identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    uploaded = []
    for file in files:
        try:
            filename = safe_filename(file.filename or "upload")
            payload = await file.read()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not payload:
            raise HTTPException(status_code=400, detail=f"{filename} is empty.")
        if len(payload) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{filename} exceeds the upload limit.")
        write_document(owner, filename, payload)
        uploaded.append(filename)
        write_audit_event(owner, "document_uploaded", filename)
    actions = [action for automation in trigger(owner, "document_uploaded") for action in automation["actions"]]
    if "auto_index" in actions:
        with materialized_documents(owner) as directory:
            result = service.ingest_directory(directory, namespace=owner)
        save_index_state(owner, result["chunks"])
    if "notify" in actions:
        notify(owner, "Document upload complete", f"{len(uploaded)} document(s) uploaded.")
    return {"uploaded": uploaded, "documents": list_documents(owner)}


@app.delete("/api/documents/{filename}")
def delete_document(filename: str, identity: dict = Depends(current_identity)) -> dict:
    try:
        path = document_path(owner_id(identity), filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    path.unlink()
    write_audit_event(owner_id(identity), "document_deleted", path.name)
    return {"status": "deleted", "documents": list_documents(owner_id(identity))}


@app.get("/api/documents/{filename}/download")
def download_document(filename: str, identity: dict = Depends(current_identity)):
    try:
        path = document_path(owner_id(identity), filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    return Response(content=read_document_bytes(owner_id(identity), filename), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{path.name}"'})


@app.post("/api/documents/ingest")
def ingest_documents(identity: dict = Depends(current_identity)) -> dict:
    owner = owner_id(identity)
    try:
        with materialized_documents(owner) as directory:
            result = service.ingest_directory(directory, namespace=owner)
        save_index_state(owner, result["chunks"])
        write_audit_event(owner, "documents_indexed", f"{result['documents']} docs / {result['chunks']} chunks")
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chat")
def chat(payload: ChatRequest, identity: dict = Depends(current_identity)) -> dict:
    try:
        enforce_rate_limit(identity)
        write_audit_event(owner_id(identity), "rag_question", "document-grounded request")
        started = perf_counter()
        namespace = permitted_namespace(payload.workspace_id, identity)
        result = service.answer(payload.message, payload.top_k, namespace=namespace, history=payload.history,
                                language=payload.language, use_web_fallback=payload.use_web_fallback,
                                memory=get_memory(owner_id(identity)), privacy_mode=payload.privacy_mode)
        result["latency_ms"] = round((perf_counter() - started) * 1000)
        record_metric(owner_id(identity), result.get("confidence", 0), result["latency_ms"], len(result.get("citations", [])), result.get("web_fallback_used", False), payload.message)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chat/stream")
def stream_chat(payload: ChatRequest, identity: dict = Depends(current_identity)):
    """Send response text in SSE chunks so the browser can render progress and cancel safely."""
    namespace = permitted_namespace(payload.workspace_id, identity)
    def events():
        try:
            started = perf_counter()
            enforce_rate_limit(identity)
            write_audit_event(owner_id(identity), "rag_question_stream", "document-grounded request")
            result = service.answer(payload.message, payload.top_k, namespace=namespace, history=payload.history,
                                    language=payload.language, use_web_fallback=payload.use_web_fallback,
                                    memory=get_memory(owner_id(identity)), privacy_mode=payload.privacy_mode)
            result["latency_ms"] = round((perf_counter() - started) * 1000)
            record_metric(owner_id(identity), result.get("confidence", 0), result["latency_ms"], len(result.get("citations", [])), result.get("web_fallback_used", False), payload.message)
            response = result.pop("response", "")
            for start in range(0, len(response), 80):
                yield f"data: {json.dumps({'type': 'delta', 'text': response[start:start + 80]})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'meta': result})}\n\n"
        except RuntimeError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/admin/overview")
def admin_overview(identity: dict = Depends(require_admin)) -> dict:
    return {"accounts": admin_document_overview()}


@app.get("/api/admin/audit")
def admin_audit(account_id: str, identity: dict = Depends(require_admin)) -> dict:
    return {"account_id": account_id, "events": audit_events(account_id)}


@app.get("/api/admin/metrics")
def metrics(identity: dict = Depends(require_admin)) -> dict:
    return admin_metrics()


@app.get("/api/admin/metrics/timeline")
def metrics_timeline(days: int = 14, identity: dict = Depends(require_admin)) -> dict:
    return {"days": admin_metrics_timeline(days=max(1, min(days, 90)))}


@app.get("/api/admin/evaluation")
def evaluation(identity: dict = Depends(require_admin)) -> dict:
    guard_results = run_guard_evaluation()
    categories = sorted({case.category for case in EVALUATION_CASES})
    return {
        "total_cases": len(EVALUATION_CASES), "categories": categories,
        "guard_passed": sum(result["passed"] for result in guard_results), "guard_total": len(guard_results),
        "status": "The remaining retrieval cases run against the current document index through the automated test suite.",
    }


@app.post("/api/admin/evaluation/run")
def run_evaluation(account_id: str, identity: dict = Depends(require_admin)) -> dict:
    """Run source-level retrieval checks for one account's current index on demand."""
    try:
        results = run_retrieval_evaluation(lambda question: service.retrieve(question, namespace=account_id))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not evaluate this index: {exc}") from exc
    snapshot = record_evaluation(account_id, results)
    history = evaluation_history(account_id)
    return {
        "account_id": account_id,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
        "snapshot": snapshot,
        "history": history,
    }


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest, identity: dict = Depends(current_identity)) -> dict:
    record_feedback(owner_id(identity), payload.message_id, payload.helpful, payload.question, payload.response)
    write_audit_event(owner_id(identity), "answer_feedback", "helpful" if payload.helpful else "needs_review")
    return {"status": "recorded"}


@app.post("/api/documents/{filename}/ask")
def ask_document(filename: str, payload: ChatRequest, identity: dict = Depends(current_identity)) -> dict:
    try:
        filename = safe_filename(filename)
        if not document_path(owner_id(identity), filename).exists():
            raise HTTPException(status_code=404, detail="Document not found.")
        enforce_rate_limit(identity)
        return service.answer(payload.message, payload.top_k, namespace=owner_id(identity), source=filename,
                              language=payload.language, history=payload.history)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/documents/{filename}/summary")
def summarize_document(filename: str, identity: dict = Depends(current_identity)) -> dict:
    request = ChatRequest(message="Provide a concise, cited summary of this document, including its key points.")
    return ask_document(filename, request, identity)
