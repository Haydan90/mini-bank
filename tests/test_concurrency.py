"""Главные тесты проекта: корректность под параллельной нагрузкой.

Идут напрямую через сервисный слой, каждая задача — в своём потоке и своей сессии БД,
поэтому реально гонятся за блокировки строк в PostgreSQL.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.errors import BankError
from app.db.session import SessionLocal
from app.models import Account, LedgerEntry, Transfer
from app.services.transfers import make_transfer
from tests.conftest import db_balance, db_create_user_with_account

WORKERS = 16
TIMEOUT = 60


def _run_transfer(user_id, from_id, to_id, amount, key=None):
    with SessionLocal() as db:
        try:
            transfer, replayed = make_transfer(
                db, user_id, key or uuid.uuid4().hex, from_id, to_id, amount
            )
            return "ok", transfer.id, replayed
        except BankError as exc:
            return "err", exc.code, False


def _run_all(jobs):
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(*job) for job in jobs]
        return [f.result(timeout=TIMEOUT) for f in futures]


def _assert_ledger_matches_balances():
    """Инвариант двойной записи: сумма проводок по каждому счёту == баланс счёта."""
    with SessionLocal() as db:
        sums = dict(
            db.execute(
                select(LedgerEntry.account_id, func.sum(LedgerEntry.amount)).group_by(
                    LedgerEntry.account_id
                )
            ).all()
        )
        for account in db.scalars(select(Account)):
            assert sums.get(account.id, 0) == account.balance


def test_parallel_transfers_conserve_money():
    user_a, acc_a = db_create_user_with_account(100)
    _, acc_b = db_create_user_with_account(0)

    results = _run_all([(_run_transfer, user_a, acc_a, acc_b, 1) for _ in range(50)])

    assert all(r[0] == "ok" for r in results)
    assert db_balance(acc_a) == 50
    assert db_balance(acc_b) == 50
    _assert_ledger_matches_balances()


def test_no_overdraft_under_contention():
    user_a, acc_a = db_create_user_with_account(50)
    _, acc_b = db_create_user_with_account(0)

    results = _run_all([(_run_transfer, user_a, acc_a, acc_b, 10) for _ in range(20)])

    ok = [r for r in results if r[0] == "ok"]
    failed = [r for r in results if r[0] == "err"]
    assert len(ok) == 5
    assert len(failed) == 15
    assert all(r[1] == "insufficient_funds" for r in failed)
    assert db_balance(acc_a) == 0
    assert db_balance(acc_b) == 50
    _assert_ledger_matches_balances()


def test_opposite_transfers_do_not_deadlock():
    user_a, acc_a = db_create_user_with_account(10_000)
    user_b, acc_b = db_create_user_with_account(10_000)

    jobs = []
    for _ in range(100):
        jobs.append((_run_transfer, user_a, acc_a, acc_b, 1))
        jobs.append((_run_transfer, user_b, acc_b, acc_a, 1))
    results = _run_all(jobs)

    assert all(r[0] == "ok" for r in results), [r for r in results if r[0] != "ok"][:3]
    assert db_balance(acc_a) == 10_000
    assert db_balance(acc_b) == 10_000
    _assert_ledger_matches_balances()


def test_same_idempotency_key_in_parallel_creates_one_transfer():
    user_a, acc_a = db_create_user_with_account(1_000)
    _, acc_b = db_create_user_with_account(0)
    key = "parallel-key-0001"

    results = _run_all([(_run_transfer, user_a, acc_a, acc_b, 300, key) for _ in range(10)])

    assert all(r[0] == "ok" for r in results)
    assert len({r[1] for r in results}) == 1  # у всех один и тот же transfer.id
    assert sum(1 for r in results if r[2] is False) == 1  # создан ровно один раз

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert db_balance(acc_a) == 700
    assert db_balance(acc_b) == 300
    _assert_ledger_matches_balances()
