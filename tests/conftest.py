import os
import uuid

# ВАЖНО: переменная окружения должна быть выставлена до импорта приложения,
# иначе engine создастся на «боевую» БД.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://bank:bank@localhost:5432/bank_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Account, User  # noqa: E402
from app.services import accounts as accounts_service  # noqa: E402

ADMIN_EMAIL = "admin@example.com"


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database():
    _ensure_test_database()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_database):
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE ledger_entries, transfers, accounts, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------- хелперы для HTTP-тестов ----------


def register_and_login(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def create_account(client: TestClient, headers: dict, currency: str = "RUB") -> str:
    resp = client.post("/accounts", json={"currency": currency}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def deposit(client: TestClient, admin_headers: dict, account_id: str, amount: int) -> None:
    resp = client.post(
        f"/accounts/{account_id}/deposit", json={"amount": amount}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text


def transfer(client, headers, from_id, to_id, amount, key=None):
    return client.post(
        "/transfers",
        json={"from_account_id": from_id, "to_account_id": to_id, "amount": amount},
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
    )


# ---------- хелперы для тестов конкурентности (без HTTP, напрямую через сервисы) ----------


def db_create_user_with_account(balance: int, currency: str = "RUB") -> tuple[uuid.UUID, uuid.UUID]:
    """Создаёт пользователя и счёт с начальным балансом (через депозит -> есть проводка)."""
    with SessionLocal() as db:
        user = User(email=f"{uuid.uuid4().hex}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        account = Account(user_id=user.id, currency=currency)
        db.add(account)
        db.commit()
        user_id, account_id = user.id, account.id
        if balance > 0:
            accounts_service.deposit(db, account_id, balance)
    return user_id, account_id


def db_balance(account_id: uuid.UUID) -> int:
    with SessionLocal() as db:
        return db.get(Account, account_id).balance
