import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    currency: Literal["RUB", "USD", "EUR"] = "RUB"


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    currency: str
    balance: int = Field(description="Баланс в минимальных единицах (копейки)")
    status: str
    created_at: datetime


class DepositRequest(BaseModel):
    amount: int = Field(gt=0, le=10**12, description="Сумма в копейках")


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: str
    transfer_id: uuid.UUID | None
    amount: int = Field(description="Со знаком: списание отрицательное (копейки)")
    balance_after: int
    created_at: datetime


class TransactionsPage(BaseModel):
    items: list[LedgerEntryOut]
    next_before_id: int | None = Field(
        description="Передай как before_id, чтобы получить следующую страницу; null — конец"
    )
