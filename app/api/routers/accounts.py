import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import User
from app.schemas.account import (
    AccountCreate,
    AccountOut,
    DepositRequest,
    LedgerEntryOut,
    TransactionsPage,
)
from app.services import accounts as accounts_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return accounts_service.open_account(db, user.id, body.currency)


@router.get("", response_model=list[AccountOut])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return accounts_service.list_accounts(db, user.id)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return accounts_service.get_owned_account(db, user.id, account_id)


@router.post("/{account_id}/deposit", response_model=AccountOut)
def deposit(
    account_id: uuid.UUID,
    body: DepositRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Демо-пополнение счёта. Только для роли admin."""
    return accounts_service.deposit(db, account_id, body.amount)


@router.get("/{account_id}/transactions", response_model=TransactionsPage)
def list_transactions(
    account_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, ge=1, description="Курсор: вернуть записи с id меньше"),
    entry_type: Literal["deposit", "transfer_in", "transfer_out"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts_service.get_owned_account(db, user.id, account_id)
    items, next_before_id = accounts_service.list_transactions(
        db,
        account_id,
        limit=limit,
        before_id=before_id,
        entry_type=entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    return TransactionsPage(
        items=[LedgerEntryOut.model_validate(item) for item in items],
        next_before_id=next_before_id,
    )
