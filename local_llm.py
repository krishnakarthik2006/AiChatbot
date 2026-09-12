from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_SELECTION_FILE = Path(__file__).resolve().parent / ".active_llm_model"


def _loaded_runtime_model() -> str | None:
    try:
        return MODEL_SELECTION_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


_runtime_model: str | None = _loaded_runtime_model()


def set_runtime_model(name: str | None) -> None:
    """Override the active Ollama model for the whole process, persisted across restarts."""
    global _runtime_model
    name = (name or "").strip()
    _runtime_model = name or None
    try:
        if name:
            MODEL_SELECTION_FILE.write_text(name, encoding="utf-8")
        else:
            MODEL_SELECTION_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def runtime_model() -> str | None:
    """Return the currently selected runtime model, if any."""
    return _runtime_model

class LocalLLMError(RuntimeError):
    """Raised when the local model runner cannot complete a request."""


class LocalLLMClient:
    """Small Ollama client for private, local-only chat generation."""

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model_from_env = bool(_runtime_model or os.getenv("OLLAMA_MODEL"))
        self.model = _runtime_model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
        self._status_cache: dict | None = None
        self._status_checked_at = 0.0

    @staticmethod
    def _chosen_model() -> str:
        return _runtime_model or LocalLLMClient.model_default()

    @classmethod
    def model_default(cls) -> str:
        return os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    def status(self, max_age: float = 10.0) -> dict:
        now = time.time()
        if self._status_cache and now - self._status_checked_at < max_age:
            return self._status_cache

        try:
            response = self._request("GET", "/api/tags", timeout=2.0)
            models = [item.get("name", "") for item in response.get("models", [])]
            available = bool(models)
            active_model = self._chosen_model()
            if available and active_model not in models and not self.model_from_env:
                active_model = models[0]
            model_ready = active_model in models if models else False
            status = {
                "available": available,
                "base_url": self.base_url,
                "model": self.model,
                "active_model": active_model,
                "model_ready": model_ready,
                "installed_models": models,
                "error": None if available else "No local models are installed.",
                "is_cloud": False,
            }
        except LocalLLMError as exc:
            status = {
                "available": False,
                "base_url": self.base_url,
                "model": self.model,
                "active_model": self.model,
                "model_ready": False,
                "installed_models": [],
                "error": str(exc),
                "is_cloud": False,
            }

        self._status_cache = status
        self._status_checked_at = now
        return status

    def chat(self, messages: list[dict], temperature: float = 0.4) -> dict:
        active_model = _runtime_model or self.model
        payload = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": max(0.0, min(float(temperature), 1.2)),
                "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "4096")),
            },
        }
        data = self._request("POST", "/api/chat", payload, timeout=self.timeout)
        message = data.get("message", {})
        content = message.get("content", "").strip()
        if not content:
            raise LocalLLMError("The local model returned an empty response.")
        return {
            "content": content,
            "model": data.get("model", active_model),
            "done_reason": data.get("done_reason", "stop"),
        }

    def describe_image(self, image_base64: str, prompt: str = "Describe this image in a few concise sentences.") -> str:
        """Ask an Ollama vision model to caption a base64-encoded image."""
        vision_model = os.getenv("OLLAMA_VISION_MODEL", "llava").strip()
        payload = {
            "model": vision_model,
            "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        data = self._request("POST", "/api/chat", payload, timeout=self.timeout)
        content = str(data.get("message", {}).get("content", "")).strip()
        if not content:
            raise LocalLLMError("The vision model returned an empty description.")
        return content

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalLLMError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LocalLLMError(
                f"Ollama is not reachable at {self.base_url}. Start Ollama or set OLLAMA_HOST."
            ) from exc
        except TimeoutError as exc:
            raise LocalLLMError("The local model timed out while generating.") from exc
        except json.JSONDecodeError as exc:
            raise LocalLLMError("Ollama returned invalid JSON.") from exc
