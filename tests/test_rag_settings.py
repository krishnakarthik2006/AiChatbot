from rag import config


def test_retrieval_settings_match_project_specification():
    assert config.CHUNK_SIZE == 2000
    assert config.CHUNK_OVERLAP == 500
    assert config.TOP_K >= 1
    assert config.RETRIEVAL_CONFIDENCE_THRESHOLD > 0
