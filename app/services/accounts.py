import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AccountClosed, AccountNotFound, Forbidden
from app.models import Account, LedgerEntry


def open_account(db: Session, user_id: uuid.UUID, currency: str) -> Account:
    account = Account(user_id=user_id, currency=currency)
    db.add(account)
    db.commit()
    return account


def list_accounts(db: Session, user_id: uuid.UUID) -> list[Account]:
    stmt = select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
    return list(db.scalars(stmt))


def get_owned_account(db: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise AccountNotFound()
    if account.user_id != user_id:
        raise Forbidden()
    return account


def deposit(db: Session, account_id: uuid.UUID, amount: int) -> Account:
    """Пополнение счёта (демо-операция, доступна admin). Строка счёта блокируется."""
    account = db.scalar(
        select(Account)
        .where(Account.id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if account is None:
        raise AccountNotFound()
    if account.status != "active":
        raise AccountClosed()

    account.balance += amount
    db.add(
        LedgerEntry(
            account_id=account.id,
            transfer_id=None,
            entry_type="deposit",
            amount=amount,
            balance_after=account.balance,
        )
    )
    db.commit()
    return account


def list_transactions(
    db: Session,
    account_id: uuid.UUID,
    *,
    limit: int,
    before_id: int | None,
    entry_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> tuple[list[LedgerEntry], int | None]:
    """Keyset-пагинация: стабильна при новых записях и не деградирует как OFFSET."""
    stmt = select(LedgerEntry).where(LedgerEntry.account_id == account_id)
    if before_id is not None:
        stmt = stmt.where(LedgerEntry.id < before_id)
    if entry_type is not None:
        stmt = stmt.where(LedgerEntry.entry_type == entry_type)
    if date_from is not None:
        stmt = stmt.where(LedgerEntry.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(LedgerEntry.created_at <= date_to)
    stmt = stmt.order_by(LedgerEntry.id.desc()).limit(limit + 1)

    rows = list(db.scalars(stmt))
    if len(rows) > limit:
        items = rows[:limit]
        return items, items[-1].id
    return rows, None
