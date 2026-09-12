from rag.service import RAGService


def test_short_followup_retrieval_uses_last_user_topic():
    history = [{"role": "user", "content": "Explain the hostel application process"}]
    assert "hostel application" in RAGService._retrieval_query("What about fees?", history)


def test_reranker_rewards_matching_query_terms():
    query_terms = {"hostel", "fees"}
    assert RAGService._term_coverage(query_terms, "Hostel fees and payment dates") > 0
    assert RAGService._term_coverage(query_terms, "A placement event") == 0
