"""Explainable model and workflow routing for ai_chatbot requests."""
from __future__ import annotations


def route_request(question: str, has_documents: bool, use_web_fallback: bool, privacy_mode: bool = False) -> dict:
    lowered = (question or "").lower()
    if privacy_mode:
        return {"engine": "local", "reason": "Privacy mode keeps this request on the local assistant."}
    if any(term in lowered for term in ("calculate", "sum ", "average", "what is ")):
        return {"engine": "agent", "reason": "The request may benefit from a controlled utility tool."}
    if has_documents:
        return {"engine": "rag", "reason": "Uploaded documents are available for grounded retrieval."}
    if use_web_fallback:
        return {"engine": "web_rag", "reason": "No document index is available and web fallback was enabled."}
    return {"engine": "rag", "reason": "Document-grounded mode is the safest available route."}
