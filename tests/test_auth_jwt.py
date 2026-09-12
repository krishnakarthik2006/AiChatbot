from types import SimpleNamespace

from flask import Flask, g, jsonify
from werkzeug.security import generate_password_hash

from backend import auth
from backend.auth import JWT_ALGORITHM, JWT_AUDIENCE, auth_required, create_access_token, decode_access_token, init_auth
from backend.models import Account


def _token_app(secret="test-secret-key-0123456789abcdef0123456789abcdef", admin_emails=""):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secret, RAG_ADMIN_EMAILS=admin_emails, JWT_ACCESS_TOKEN_MINUTES=30)
    return app


def _account(email="user@example.com", account_id=7):
    return Account(id=account_id, email=email, password_hash="not-used", created_at="2024-01-01T00:00:00Z")


def test_token_roundtrip_includes_claims():
    app = _token_app()
    with app.app_context():
        token = create_access_token(_account())
        claims = decode_access_token(token)
    assert claims["sub"] == "7"
    assert claims["email"] == "user@example.com"
    assert claims["is_admin"] is False
    assert claims["aud"] == JWT_AUDIENCE


def test_admin_flag_read_from_configured_emails():
    app = _token_app(admin_emails="admin@example.com")
    with app.app_context():
        claims = decode_access_token(create_access_token(_account(email="ADMIN@example.com")))
    assert claims["is_admin"] is True


def test_tampered_token_rejected():
    app = _token_app()
    with app.app_context():
        token = create_access_token(_account())
        tampered = token[:-2] + "ab" if not token.endswith("ab") else token[:-2] + "cd"
        assert decode_access_token(tampered) is None


def test_wrong_secret_rejected():
    with _token_app(secret="secret-a-0123456789abcdef0123456789abcdef").app_context():
        token = create_access_token(_account())
    with _token_app(secret="secret-b-0123456789abcdef0123456789abcdef").app_context():
        assert decode_access_token(token) is None


def test_expired_token_rejected():
    app = _token_app()
    with app.app_context():
        token = create_access_token(_account(), expires_minutes=-1)
        assert decode_access_token(token) is None


def test_token_lifetime_matches_configured_minutes():
    app = _token_app()
    with app.app_context():
        assert auth.token_lifetime_seconds() == 1800


def _authenticated_app(monkeypatch):
    """A small Flask app with a real login route and an @auth_required demo view."""
    account = Account(
        id=5,
        email="user@example.com",
        password_hash=generate_password_hash("password123"),
        display_name="Tester",
        created_at="2024-01-01T00:00:00Z",
    )
    monkeypatch.setattr(auth, "get_account_by_email", lambda email: account if email == account.email else None)
    monkeypatch.setattr(auth, "get_account_by_id", lambda account_id: account if str(account_id) == str(account.id) else None)

    app = _token_app()
    init_auth(app)

    @app.route("/api/protected")
    @auth_required
    def protected():
        return jsonify({"account_id": g.account.id})

    return app, account


def test_login_returns_jwt_and_bearer_access_allowed(monkeypatch):
    app, account = _authenticated_app(monkeypatch)
    client = app.test_client()

    response = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["user"]["email"] == "user@example.com"
    assert body["access_token"]

    bearer = client.get("/api/protected", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert bearer.status_code == 200
    assert bearer.get_json()["account_id"] == account.id


def test_jwt_cookie_authenticates_subsequent_requests(monkeypatch):
    app, account = _authenticated_app(monkeypatch)
    client = app.test_client()

    response = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 200

    protected = client.get("/api/protected")
    assert protected.status_code == 200
    assert protected.get_json()["account_id"] == account.id


def test_protected_route_rejects_without_credentials(monkeypatch):
    app, _ = _authenticated_app(monkeypatch)
    response = app.test_client().get("/api/protected")
    assert response.status_code == 401
    assert response.get_json()["authenticated"] is False


def test_logout_clears_access_token_cookie(monkeypatch):
    app, _ = _authenticated_app(monkeypatch)
    client = app.test_client()
    client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    protected = client.get("/api/protected")
    assert protected.status_code == 401


def test_refresh_issues_fresh_access_token(monkeypatch):
    app, _ = _authenticated_app(monkeypatch)
    client = app.test_client()
    client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    token = refreshed.get_json()["access_token"]
    with app.app_context():
        assert decode_access_token(token) is not None
