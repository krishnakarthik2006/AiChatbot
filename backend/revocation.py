"""File-backed JWT revocation registry shared by the Flask and RAG services."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from time import time

BASE_DIR = Path(__file__).resolve().parent.parent
REVOCATION_FILE = Path(os.getenv("JWT_REVOCATION_FILE", str(BASE_DIR / ".jwt_blacklist.json")))
_lock = threading.Lock()


def _load() -> dict:
    try:
        return json.loads(REVOCATION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(registry: dict) -> None:
    try:
        REVOCATION_FILE.write_text(json.dumps(registry), encoding="utf-8")
    except OSError:
        pass


def revoke_jti(jti: str, expires_at: int) -> None:
    if not jti:
        return
    with _lock:
        registry = _load()
        registry[jti] = expires_at
        now = int(time())
        pruned = {key: value for key, value in registry.items() if value and value > now}
        _save(pruned)


def is_jti_revoked(jti) -> bool:
    if not jti:
        return False
    with _lock:
        return _load().get(str(jti), 0) > int(time())


def revoke_token(token: str, secret: str, algorithm: str = "HS256", audience: str | None = None) -> bool:
    """Record a token's jti as revoked without requiring the token still be valid."""
    import jwt

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            audience=audience,
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return False
    jti = payload.get("jti")
    if not jti:
        return False
    revoke_jti(str(jti), int(payload.get("exp", 0)) or int(time()) + 60)
    return True