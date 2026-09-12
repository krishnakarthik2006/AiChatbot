import os
import tempfile

import local_llm
from local_llm import LocalLLMClient, runtime_model, set_runtime_model


def test_runtime_model_switch_updates_new_clients(monkeypatch, tmp_path):
    monkeypatch.setattr(local_llm, "MODEL_SELECTION_FILE", tmp_path / ".active_llm_model")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    set_runtime_model("llama3.1:8b")
    assert runtime_model() == "llama3.1:8b"
    client = LocalLLMClient()
    assert client.model == "llama3.1:8b"
    assert client.model_from_env is True

    set_runtime_model("")
    assert runtime_model() is None
    assert LocalLLMClient().model == "llama3.2:3b"


def test_runtime_model_persists_across_instances(monkeypatch, tmp_path):
    selection_file = tmp_path / ".active_llm_model"
    monkeypatch.setattr(local_llm, "MODEL_SELECTION_FILE", selection_file)

    set_runtime_model("gemma2:9b")
    assert selection_file.read_text(encoding="utf-8").strip() == "gemma2:9b"

    # fresh module state (simulated) loads the persisted selection
    monkeypatch.setattr(local_llm, "_runtime_model", local_llm._loaded_runtime_model())
    assert local_llm._runtime_model == "gemma2:9b"
    assert LocalLLMClient().model == "gemma2:9b"
    set_runtime_model("")


def test_chat_uses_runtime_model_when_set(monkeypatch, tmp_path):
    monkeypatch.setattr(local_llm, "MODEL_SELECTION_FILE", tmp_path / ".active_llm_model")
    client = LocalLLMClient()

    monkeypatch.setattr(client, "_request", lambda method, path, payload=None, timeout=None: {
        "message": {"content": "ok"},
        "model": payload.get("model"),
    })
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    set_runtime_model("qwen2.5:7b")
    assert client.chat([{"role": "user", "content": "hi"}])["model"] == "qwen2.5:7b"
    set_runtime_model("")