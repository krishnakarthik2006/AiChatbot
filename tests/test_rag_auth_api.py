"""JWT protection of the FastAPI RAG gateway, exercised through TestClient."""
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

import rag_api
from backend import revocation
from rag import config

TEST_SECRET = "test-secret-key-0123456789abcdef0123456789abcdef"


def _token(email="user@example.com", account_id="1", is_admin=False, expires=None, jti=None):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(account_id),
            "email": email,
            "is_admin": is_admin,
            "iat": now,
            "exp": expires if expires is not None else now + 3600,
            "aud": "ai_chatbot:api",
            "jti": jti or os.urandom(8).hex(),
        },
        TEST_SECRET,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    for attr in ("USER_DOCUMENTS_DIR", "CHROMA_DIR", "ADMIN_DATA_DIR"):
        setattr(config, attr, tmp_path / attr)
    monkeypatch.setattr(revocation, "REVOCATION_FILE", tmp_path / ".jwt_blacklist.json")


@pytest.fixture()
def client():
    return TestClient(rag_api.app)


def test_rag_documents_requires_jwt(client):
    response = client.get("/api/documents")
    assert response.status_code == 401


def test_rag_rejects_bad_or_expired_token(client):
    bad = client.get("/api/documents", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    expired = _token(expires=int(time.time()) - 10)
    response = client.get("/api/documents", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_rag_valid_token_allowed(client):
    token = _token()
    response = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_rag_admin_endpoint_requires_role(client):
    response = client.get("/api/admin/quotas", headers={"Authorization": f"Bearer {_token(is_admin=False)}"})
    assert response.status_code == 403


def test_rag_admin_token_allowed(client):
    token = _token(is_admin=True)
    response = client.get("/api/admin/quotas", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "limit" in response.json()


def test_rag_revoked_token_rejected(client):
    jti = os.urandom(8).hex()
    token = _token(jti=jti)
    assert client.get("/api/documents", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    revocation.revoke_jti(jti, int(time.time()) + 3600)
    response = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401