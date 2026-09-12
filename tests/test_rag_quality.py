import os
import sys

from rag import config
from rag.retrieval import BM25
from rag.service import RAGService, RetrievedChunk


def test_short_followup_retrieval_uses_last_user_topic():
    history = [{"role": "user", "content": "Explain the hostel application process"}]
    assert "hostel application" in RAGService._retrieval_query("What about fees?", history)


def test_reranker_rewards_matching_query_terms():
    query_terms = {"hostel", "fees"}
    assert RAGService._term_coverage(query_terms, "Hostel fees and payment dates") > 0
    assert RAGService._term_coverage(query_terms, "A placement event") == 0


def test_rewrite_falls_back_when_no_generator_reachable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(config, "QUERY_REWRITE_ENABLED", True)

    class _NoModel:
        def status(self):
            return {"model_ready": False}

        def chat(self, *args, **kwargs):
            raise RuntimeError("no model")

    monkeypatch.setattr("rag.service.LocalLLMClient", _NoModel)
    service = RAGService()
    history = [{"role": "user", "content": "Explain the hostel application process"}]
    query = service._rewrite_query("What about fees?", history)
    assert "hostel application" in query


def test_rewrite_noop_for_long_or_first_question(monkeypatch):
    monkeypatch.setattr(config, "QUERY_REWRITE_ENABLED", True)
    service = RAGService()
    long_question = " ".join(["word"] * 9)
    assert service._rewrite_query(long_question, [{"role": "user", "content": "context"}]) == long_question
    assert service._rewrite_query("What about fees?", []) == "What about fees?"


def test_bm25_ranks_higher_term_overlap_first():
    bm25 = BM25(["Hostel fees and payment dates", "Placement event details"])
    scores = bm25.score("hostel fees")
    assert scores[0] > scores[1]


def test_bm25_empty_corpus():
    bm25 = BM25([])
    assert bm25.score("any query") == []


def _make_chunk(text):
    return RetrievedChunk(content=text, source="s.txt", chunk_id=text[:8])


def test_rerank_disabled_keeps_order(monkeypatch):
    monkeypatch.setattr(config, "RERANK_ENABLED", False)
    chunks = [_make_chunk("first"), _make_chunk("second")]
    assert RAGService()._rerank("query", chunks, 2) == chunks


def test_rerank_quietly_skips_when_library_missing(monkeypatch):
    monkeypatch.setattr(config, "RERANK_ENABLED", True)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    chunks = [_make_chunk("first"), _make_chunk("second")]
    assert RAGService()._rerank("query", chunks, 2) == chunks
