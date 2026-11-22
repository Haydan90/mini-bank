import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.transfer import TransferCreate, TransferOut
from app.services import transfers as transfers_service

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(
    body: TransferCreate,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Перевод между счетами. Повтор с тем же `Idempotency-Key` вернёт тот же результат."""
    transfer, replayed = transfers_service.make_transfer(
        db,
        user.id,
        idempotency_key,
        body.from_account_id,
        body.to_account_id,
        body.amount,
    )
    response.headers["Idempotent-Replayed"] = "true" if replayed else "false"
    return transfer


@router.get("/{transfer_id}", response_model=TransferOut)
def get_transfer(
    transfer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transfers_service.get_owned_transfer(db, user.id, transfer_id)
