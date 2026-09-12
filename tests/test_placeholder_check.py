from backend.config import _looks_like_placeholder, check_env_placeholders


def test_placeholder_values_flagged():
    assert _looks_like_placeholder("change-me-to-a-long-random-string") is True
    assert _looks_like_placeholder("dev-secret-change-in-production") is True
    assert _looks_like_placeholder("your-key-here") is True
    assert _looks_like_placeholder("") is True


def test_real_values_not_flagged():
    assert _looks_like_placeholder("6f0df149b348c0e2f38e363bb52f61f685436fa29025f45b32b020a8b6c91512") is False
    assert _looks_like_placeholder("gsk_abc123real") is False


def test_check_reports_environment_placeholders(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "your-key-here")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_real_key")
    problems = check_env_placeholders()
    keys = [problem["key"] for problem in problems]
    assert "SECRET_KEY" in keys
    assert "GROQ_API_KEY" not in keys


def test_check_clean_when_env_configured(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "6f0df149b348c0e2f38e363bb52f61f685436fa29025f45b32b020a8b6c91512")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_real_key")
    assert check_env_placeholders() == []