import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    AccountClosed,
    AccountNotFound,
    CurrencyMismatch,
    Forbidden,
    IdempotencyKeyReuse,
    InsufficientFunds,
    TransferNotFound,
)
from app.models import Account, LedgerEntry, Transfer


def _request_hash(from_id: uuid.UUID, to_id: uuid.UUID, amount: int) -> str:
    raw = f"{from_id}:{to_id}:{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _find_by_key(db: Session, user_id: uuid.UUID, key: str) -> Transfer | None:
    return db.scalar(
        select(Transfer).where(Transfer.user_id == user_id, Transfer.idempotency_key == key)
    )


def _check_same_request(transfer: Transfer, request_hash: str) -> None:
    """Тот же ключ с другим телом запроса — это ошибка клиента, а не повтор."""
    if transfer.request_hash != request_hash:
        raise IdempotencyKeyReuse()


def _execute(
    db: Session,
    user_id: uuid.UUID,
    key: str,
    request_hash: str,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    amount: int,
) -> tuple[Transfer, bool]:
    """Тело перевода. Возвращает (перевод, replayed). Коммит делает вызывающий код."""
    # 1. Блокируем оба счёта В ПОРЯДКЕ id. Одинаковый порядок у всех транзакций
    #    исключает дедлок при встречных переводах A->B и B->A.
    stmt = (
        select(Account)
        .where(Account.id.in_([from_id, to_id]))
        .order_by(Account.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    accounts = {account.id: account for account in db.scalars(stmt)}

    # 2. Повторная проверка ключа ПОСЛЕ блокировки. Параллельный запрос с тем же
    #    ключом ждал на блокировке; теперь первый уже закоммичен и мы его видим.
    existing = _find_by_key(db, user_id, key)
    if existing is not None:
        return existing, True

    src = accounts.get(from_id)
    dst = accounts.get(to_id)
    if src is None or dst is None:
        raise AccountNotFound()
    if src.user_id != user_id:
        raise Forbidden("Нельзя списывать деньги с чужого счёта")
    if src.status != "active" or dst.status != "active":
        raise AccountClosed()
    if src.currency != dst.currency:
        raise CurrencyMismatch()
    if src.balance < amount:
        raise InsufficientFunds()

    # 3. Меняем балансы (строки заблокированы, значения актуальны).
    src.balance -= amount
    dst.balance += amount

    transfer = Transfer(
        id=uuid.uuid4(),
        user_id=user_id,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=amount,
        currency=src.currency,
        status="completed",
        idempotency_key=key,
        request_hash=request_hash,
    )
    db.add(transfer)
    db.flush()  # transfer должен существовать до проводок (внешний ключ)

    # 4. Двойная запись: две проводки на каждый перевод.
    db.add_all(
        [
            LedgerEntry(
                account_id=src.id,
                transfer_id=transfer.id,
                entry_type="transfer_out",
                amount=-amount,
                balance_after=src.balance,
            ),
            LedgerEntry(
                account_id=dst.id,
                transfer_id=transfer.id,
                entry_type="transfer_in",
                amount=amount,
                balance_after=dst.balance,
            ),
        ]
    )
    return transfer, False


def make_transfer(
    db: Session,
    user_id: uuid.UUID,
    key: str,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    amount: int,
) -> tuple[Transfer, bool]:
    """Атомарный идемпотентный перевод. Возвращает (перевод, replayed)."""
    request_hash = _request_hash(from_id, to_id, amount)

    # Быстрый путь: повтор уже выполненного запроса, блокировки не нужны.
    existing = _find_by_key(db, user_id, key)
    if existing is not None:
        _check_same_request(existing, request_hash)
        db.commit()  # закрываем read-транзакцию (объекты не протухают: expire_on_commit=False)
        return existing, True

    try:
        transfer, replayed = _execute(db, user_id, key, request_hash, from_id, to_id, amount)
        _check_same_request(transfer, request_hash)
        db.commit()
        return transfer, replayed
    except IntegrityError:
        # Редкий случай: тот же ключ, но другие счета (блокировки не пересеклись),
        # а UNIQUE (user_id, idempotency_key) сработал уже при вставке.
        db.rollback()
        existing = _find_by_key(db, user_id, key)
        if existing is None:
            raise
        _check_same_request(existing, request_hash)
        db.commit()
        return existing, True
    except Exception:
        db.rollback()
        raise


def get_owned_transfer(db: Session, user_id: uuid.UUID, transfer_id: uuid.UUID) -> Transfer:
    transfer = db.get(Transfer, transfer_id)
    if transfer is None or transfer.user_id != user_id:
        raise TransferNotFound()
    return transfer
