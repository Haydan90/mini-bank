import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # Последняя линия обороны: даже при баге в коде баланс не уйдёт в минус.
        CheckConstraint("balance >= 0", name="ck_accounts_balance_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", server_default="RUB")
    # Деньги хранятся в минимальных единицах (копейки), а не во float.
    balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
