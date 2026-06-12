from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import logging

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)

class LocalLLMError(RuntimeError):
    """Raised when the local model runner cannot complete a request."""


class LocalLLMClient:
    """Small Ollama client for private, local-only chat generation."""

    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.use_gemini = bool(self.gemini_api_key and HAS_GEMINI)
        if self.use_gemini:
            genai.configure(api_key=self.gemini_api_key)

        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model_from_env = bool(os.getenv("OLLAMA_MODEL"))
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
        self._status_cache: dict | None = None
        self._status_checked_at = 0.0

    def status(self, max_age: float = 10.0) -> dict:
        if self.use_gemini:
            return {
                "available": True,
                "base_url": "https://generativelanguage.googleapis.com",
                "model": "gemini-1.5-flash",
                "active_model": "gemini-1.5-flash",
                "model_ready": True,
                "installed_models": ["gemini-1.5-flash"],
                "error": None,
                "is_cloud": True
            }

        now = time.time()
        if self._status_cache and now - self._status_checked_at < max_age:
            return self._status_cache

        try:
            response = self._request("GET", "/api/tags", timeout=2.0)
            models = [item.get("name", "") for item in response.get("models", [])]
            available = bool(models)
            active_model = self.model
            if available and self.model not in models and not self.model_from_env:
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
            }

        self._status_cache = status
        self._status_checked_at = now
        return status

    def chat(self, messages: list[dict], temperature: float = 0.4) -> dict:
        if self.use_gemini:
            return self._chat_gemini(messages, temperature)

        active_model = self.status().get("active_model", self.model)
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

    def _chat_gemini(self, messages: list[dict], temperature: float) -> dict:
        try:
            contents = []
            system_instruction = ""
            for msg in messages:
                role = msg.get("role")
                if role == "system":
                    system_instruction += msg.get("content", "") + "\n"
                elif role == "user":
                    contents.append({"role": "user", "parts": [msg.get("content", "")]})
                elif role in ("assistant", "bot"):
                    contents.append({"role": "model", "parts": [msg.get("content", "")]})

            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_instruction.strip() if system_instruction else None
            )

            response = model.generate_content(
                contents,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                )
            )
            
            return {
                "content": response.text.strip(),
                "model": "gemini-1.5-flash",
                "done_reason": "stop"
            }
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            raise LocalLLMError(f"Gemini API failed: {e}")

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
