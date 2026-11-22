from tests.conftest import ADMIN_EMAIL, create_account, deposit, register_and_login


def test_create_and_list_accounts(client):
    headers = register_and_login(client, "u1@example.com")
    acc_id = create_account(client, headers)
    accounts = client.get("/accounts", headers=headers).json()
    assert [a["id"] for a in accounts] == [acc_id]
    assert accounts[0]["balance"] == 0
    assert accounts[0]["currency"] == "RUB"


def test_cannot_read_foreign_account(client):
    h1 = register_and_login(client, "u1@example.com")
    h2 = register_and_login(client, "u2@example.com")
    acc_id = create_account(client, h1)
    resp = client.get(f"/accounts/{acc_id}", headers=h2)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_deposit_requires_admin(client):
    h_user = register_and_login(client, "u1@example.com")
    acc_id = create_account(client, h_user)
    resp = client.post(f"/accounts/{acc_id}/deposit", json={"amount": 100}, headers=h_user)
    assert resp.status_code == 403


def test_admin_deposit_and_history(client):
    h_admin = register_and_login(client, ADMIN_EMAIL)
    h_user = register_and_login(client, "u1@example.com")
    acc_id = create_account(client, h_user)

    deposit(client, h_admin, acc_id, 10_000)

    assert client.get(f"/accounts/{acc_id}", headers=h_user).json()["balance"] == 10_000
    page = client.get(f"/accounts/{acc_id}/transactions", headers=h_user).json()
    assert len(page["items"]) == 1
    assert page["items"][0]["entry_type"] == "deposit"
    assert page["items"][0]["amount"] == 10_000
    assert page["items"][0]["balance_after"] == 10_000
    assert page["next_before_id"] is None


def test_deposit_validation(client):
    h_admin = register_and_login(client, ADMIN_EMAIL)
    h_user = register_and_login(client, "u1@example.com")
    acc_id = create_account(client, h_user)
    for bad in (0, -5):
        resp = client.post(f"/accounts/{acc_id}/deposit", json={"amount": bad}, headers=h_admin)
        assert resp.status_code == 422
