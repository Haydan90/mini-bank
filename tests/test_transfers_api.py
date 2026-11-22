import uuid

from tests.conftest import ADMIN_EMAIL, create_account, deposit, register_and_login, transfer


def _setup(client, amount=10_000):
    h_admin = register_and_login(client, ADMIN_EMAIL)
    h1 = register_and_login(client, "alice@example.com")
    h2 = register_and_login(client, "bob@example.com")
    a1 = create_account(client, h1)
    a2 = create_account(client, h2)
    deposit(client, h_admin, a1, amount)
    return h_admin, h1, h2, a1, a2


def _balance(client, headers, account_id):
    return client.get(f"/accounts/{account_id}", headers=headers).json()["balance"]


def test_successful_transfer_updates_balances_and_ledger(client):
    _, h1, h2, a1, a2 = _setup(client)

    resp = transfer(client, h1, a1, a2, 2_500)
    assert resp.status_code == 201, resp.text
    assert resp.json()["amount"] == 2_500
    assert resp.headers["Idempotent-Replayed"] == "false"

    assert _balance(client, h1, a1) == 7_500
    assert _balance(client, h2, a2) == 2_500

    out = client.get(f"/accounts/{a1}/transactions", headers=h1).json()["items"]
    assert [e["entry_type"] for e in out] == ["transfer_out", "deposit"]
    assert out[0]["amount"] == -2_500 and out[0]["balance_after"] == 7_500

    inc = client.get(f"/accounts/{a2}/transactions", headers=h2).json()["items"]
    assert inc[0]["entry_type"] == "transfer_in" and inc[0]["amount"] == 2_500


def test_insufficient_funds(client):
    _, h1, _, a1, a2 = _setup(client, amount=1_000)
    resp = transfer(client, h1, a1, a2, 1_001)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "insufficient_funds"
    assert _balance(client, h1, a1) == 1_000


def test_cannot_transfer_from_foreign_account(client):
    _, h1, h2, a1, a2 = _setup(client)
    resp = transfer(client, h2, a1, a2, 100)  # bob пытается списать со счёта alice
    assert resp.status_code == 403
    assert _balance(client, h1, a1) == 10_000


def test_unknown_account_returns_404(client):
    _, h1, _, a1, _ = _setup(client)
    resp = transfer(client, h1, a1, str(uuid.uuid4()), 100)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "account_not_found"


def test_same_account_is_422(client):
    _, h1, _, a1, _ = _setup(client)
    assert transfer(client, h1, a1, a1, 100).status_code == 422


def test_non_positive_amount_is_422(client):
    _, h1, _, a1, a2 = _setup(client)
    assert transfer(client, h1, a1, a2, 0).status_code == 422
    assert transfer(client, h1, a1, a2, -100).status_code == 422


def test_currency_mismatch(client):
    _, h1, h2, a1, _ = _setup(client)
    usd = create_account(client, h2, currency="USD")
    resp = transfer(client, h1, a1, usd, 100)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "currency_mismatch"


def test_idempotency_key_header_is_required(client):
    _, h1, _, a1, a2 = _setup(client)
    resp = client.post(
        "/transfers",
        json={"from_account_id": a1, "to_account_id": a2, "amount": 100},
        headers=h1,
    )
    assert resp.status_code == 422


def test_idempotent_replay_does_not_double_charge(client):
    _, h1, h2, a1, a2 = _setup(client)
    key = "order-12345-payment"

    first = transfer(client, h1, a1, a2, 3_000, key=key)
    second = transfer(client, h1, a1, a2, 3_000, key=key)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.headers["Idempotent-Replayed"] == "false"
    assert second.headers["Idempotent-Replayed"] == "true"
    assert _balance(client, h1, a1) == 7_000
    assert _balance(client, h2, a2) == 3_000


def test_same_key_with_different_body_is_rejected(client):
    _, h1, _, a1, a2 = _setup(client)
    key = "order-777-payment"
    assert transfer(client, h1, a1, a2, 100, key=key).status_code == 201
    resp = transfer(client, h1, a1, a2, 200, key=key)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "idempotency_key_reused"
    assert _balance(client, h1, a1) == 9_900


def test_get_transfer_is_scoped_to_owner(client):
    _, h1, h2, a1, a2 = _setup(client)
    transfer_id = transfer(client, h1, a1, a2, 100).json()["id"]
    assert client.get(f"/transfers/{transfer_id}", headers=h1).status_code == 200
    assert client.get(f"/transfers/{transfer_id}", headers=h2).status_code == 404


def test_history_pagination_and_filters(client):
    _, h1, _, a1, a2 = _setup(client, amount=100_000)
    for _ in range(5):
        assert transfer(client, h1, a1, a2, 100).status_code == 201
    # всего 6 проводок на a1: 1 депозит + 5 списаний

    seen = []
    cursor = None
    while True:
        params = {"limit": 2}
        if cursor:
            params["before_id"] = cursor
        page = client.get(f"/accounts/{a1}/transactions", params=params, headers=h1).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_before_id"]
        if cursor is None:
            break

    assert len(seen) == 6
    assert seen == sorted(seen, reverse=True)
    assert len(set(seen)) == 6

    only_out = client.get(
        f"/accounts/{a1}/transactions", params={"entry_type": "transfer_out"}, headers=h1
    ).json()["items"]
    assert len(only_out) == 5
