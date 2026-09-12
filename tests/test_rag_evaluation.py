from types import SimpleNamespace

from rag.evaluation import EVALUATION_CASES, run_guard_evaluation, run_retrieval_evaluation


def test_evaluation_suite_has_over_thirty_retrieval_robustness_and_security_cases():
    assert len(EVALUATION_CASES) >= 30
    assert {"retrieval", "robustness", "security", "chunk_boundary", "document_update", "contradictory_documents", "hallucination"} <= {
        item.category for item in EVALUATION_CASES
    }


def test_all_injection_cases_are_blocked():
    assert all(result["passed"] for result in run_guard_evaluation())


def test_retrieval_evaluation_scores_expected_source_from_citations():
    results = run_retrieval_evaluation(lambda question: [SimpleNamespace(source="hostel-policy.pdf")])
    hostel_results = [result for result in results if "hostel" in result["id"]]
    assert hostel_results and all(result["passed"] for result in hostel_results)
