from tests.conftest import register_and_login


def test_register_and_login(client):
    headers = register_and_login(client, "user1@example.com")
    resp = client.get("/accounts", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post(
        "/auth/register", json={"email": "DUP@example.com", "password": "password123"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


def test_register_short_password_is_422(client):
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "123"})
    assert resp.status_code == 422


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "u@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "u@example.com", "password": "wrong-pass"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_protected_endpoint_requires_token(client):
    assert client.get("/accounts").status_code == 401
    assert client.get("/accounts", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
