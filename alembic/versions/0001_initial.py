"""initial schema: users, accounts, transfers, ledger_entries

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("balance >= 0", name="ck_accounts_balance_non_negative"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    op.create_table(
        "transfers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("to_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount > 0", name="ck_transfers_amount_positive"),
        sa.CheckConstraint(
            "from_account_id <> to_account_id", name="ck_transfers_different_accounts"
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_transfers_user_idempotency_key"),
    )
    op.create_index("ix_transfers_user_id", "transfers", ["user_id"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), sa.ForeignKey("transfers.id"), nullable=True),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ledger_account_id_id", "ledger_entries", ["account_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_account_id_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_transfers_user_id", table_name="transfers")
    op.drop_table("transfers")
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
