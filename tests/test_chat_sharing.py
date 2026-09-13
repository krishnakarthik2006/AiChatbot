import app as server
from backend import database as db


def _register_and_login(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 201, response.get_json()
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.get_json()
    return login.get_json()["user"]["id"]


def _seed_chat(client, account_id):
    session = client.post("/api/session", json={})
    assert session.status_code == 200, session.get_json()
    session_id = session.get_json()["session_id"]
    user = db.get_user_for_account(session_id, account_id)
    db.save_conversation(
        user.id, "What is the flux capacitor?", "The flux capacitor stores 1.21 gigawatts.", "topic",
        0.9, "local_llm", "llama3.2:3b",
    )
    return session_id


def test_share_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_path", lambda: tmp_path / "local_store.json")
    client = server.app.test_client()
    account_id = _register_and_login(client, "owner@example.com")
    _seed_chat(client, account_id)

    created = client.post("/api/shares", json={})
    assert created.status_code == 201, created.get_json()
    share = created.get_json()["share"]
    token = share["token"]
    assert share["message_count"] == 2
    assert share["url"].endswith(f"/share/{token}")

    public = client.get(f"/api/share/{token}")
    assert public.status_code == 200
    payload = public.get_json()
    assert payload["title"]
    assert [m["sender"] for m in payload["messages"]] == ["user", "bot"]
    assert payload["messages"][0]["text"] == "What is the flux capacitor?"

    listed = client.get("/api/shares")
    assert listed.status_code == 200
    assert len(listed.get_json()["shares"]) == 1

    revoked = client.delete(f"/api/shares/{token}")
    assert revoked.status_code == 200

    gone = client.get(f"/api/share/{token}")
    assert gone.status_code == 404


def test_share_requires_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_path", lambda: tmp_path / "local_store.json")
    client = server.app.test_client()
    account_id = _register_and_login(client, "owner@example.com")
    _seed_chat(client, account_id)

    created = client.post("/api/shares", json={})
    token = created.get_json()["share"]["token"]

    other = server.app.test_client()
    _register_and_login(other, "other@example.com")
    assert other.delete(f"/api/shares/{token}").status_code == 404


def test_share_public_access_requires_no_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_path", lambda: tmp_path / "local_store.json")
    client = server.app.test_client()
    account_id = _register_and_login(client, "owner@example.com")
    _seed_chat(client, account_id)

    created = client.post("/api/shares", json={})
    token = created.get_json()["share"]["token"]

    anonymous = server.app.test_client()
    assert anonymous.get(f"/api/share/{token}").status_code == 200


def test_share_empty_chat_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_path", lambda: tmp_path / "local_store.json")
    client = server.app.test_client()
    _register_and_login(client, "empty@example.com")
    client.post("/api/session", json={})

    response = client.post("/api/shares", json={})
    assert response.status_code == 400
    assert "no messages" in response.get_json()["error"].lower()


def test_share_routes_require_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_path", lambda: tmp_path / "local_store.json")
    anonymous = server.app.test_client()
    assert anonymous.post("/api/shares", json={}).status_code == 401
    assert anonymous.get("/api/shares").status_code == 401
    assert anonymous.delete("/api/shares/some-token").status_code == 401