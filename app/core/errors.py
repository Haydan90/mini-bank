class BankError(Exception):
    """Базовая доменная ошибка. Превращается в ответ {"error": {"code", "message"}}."""

    status_code = 400
    code = "bank_error"
    message = "Ошибка операции"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class EmailTaken(BankError):
    status_code = 409
    code = "email_taken"
    message = "Пользователь с таким email уже существует"


class InvalidCredentials(BankError):
    status_code = 401
    code = "invalid_credentials"
    message = "Неверный email или пароль"


class AccountNotFound(BankError):
    status_code = 404
    code = "account_not_found"
    message = "Счёт не найден"


class TransferNotFound(BankError):
    status_code = 404
    code = "transfer_not_found"
    message = "Перевод не найден"


class Forbidden(BankError):
    status_code = 403
    code = "forbidden"
    message = "Недостаточно прав для этой операции"


class AccountClosed(BankError):
    status_code = 422
    code = "account_closed"
    message = "Счёт закрыт"


class CurrencyMismatch(BankError):
    status_code = 422
    code = "currency_mismatch"
    message = "Валюты счетов не совпадают"


class InsufficientFunds(BankError):
    status_code = 422
    code = "insufficient_funds"
    message = "Недостаточно средств на счёте"


class IdempotencyKeyReuse(BankError):
    status_code = 422
    code = "idempotency_key_reused"
    message = "Этот Idempotency-Key уже использован с другими параметрами запроса"
