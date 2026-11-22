from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import EmailTaken, InvalidCredentials
from app.core.security import hash_password, verify_password
from app.models import User


def register_user(db: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailTaken()

    role = "admin" if email == settings.admin_email.lower() else "user"
    user = User(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # гонка: параллельная регистрация того же email
        db.rollback()
        raise EmailTaken() from None
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user
