"""Shared JWT verification for the Flask UI and FastAPI RAG service."""
from __future__ import annotations

import os
from collections import defaultdict, deque
from time import monotonic
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException

load_dotenv()
REQUESTS_BY_ACCOUNT = defaultdict(deque)
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "ai_chatbot:api"


def current_identity(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="A signed ai_chatbot JWT is required.")
    token = authorization.removeprefix("Bearer ").strip()
    secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="The ai_chatbot token is invalid or expired.") from exc
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="The ai_chatbot token is invalid.")
    return {"account_id": payload["sub"], "email": payload.get("email"), "is_admin": payload.get("is_admin", False)}


def require_admin(identity: dict = Depends(current_identity)) -> dict:
    if not identity.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return identity


def enforce_rate_limit(identity: dict, limit: int = 30, window_seconds: int = 60) -> None:
    """Small in-process limiter for local deployments; rejects bursts before model execution."""
    now = monotonic()
    requests = REQUESTS_BY_ACCOUNT[str(identity["account_id"])]
    while requests and now - requests[0] > window_seconds:
        requests.popleft()
    if len(requests) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")
    requests.append(now)
