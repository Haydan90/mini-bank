import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int = Field(gt=0, le=10**12, description="Сумма в копейках")

    @model_validator(mode="after")
    def accounts_must_differ(self) -> "TransferCreate":
        if self.from_account_id == self.to_account_id:
            raise ValueError("Нельзя переводить на тот же счёт")
        return self


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int
    currency: str
    status: str
    created_at: datetime
