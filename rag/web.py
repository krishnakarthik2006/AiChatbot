"""Optional cited web-search fallback. It is disabled unless the caller opts in."""
from __future__ import annotations

from .service import RetrievedChunk


def search_web(question: str, limit: int = 4) -> list[RetrievedChunk]:
    try:
        from duckduckgo_search import DDGS
    except ImportError as exc:
        raise RuntimeError("Web fallback requires duckduckgo-search. Install project requirements.") from exc
    results = DDGS().text(question, max_results=limit)
    return [
        RetrievedChunk(
            content=item.get("body", ""), source=item.get("href", "web result"),
            chunk_id=f"web-{index}", score=0.5,
        )
        for index, item in enumerate(results, 1) if item.get("body")
    ]
