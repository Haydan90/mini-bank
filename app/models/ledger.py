import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LedgerEntry(Base):
    """Журнал проводок. Сумма проводок по счёту всегда равна его балансу."""

    __tablename__ = "ledger_entries"
    __table_args__ = (Index("ix_ledger_account_id_id", "account_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfers.id"), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(16))  # transfer_out | transfer_in | deposit
    amount: Mapped[int] = mapped_column(BigInteger)  # со знаком: списание отрицательное
    balance_after: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
