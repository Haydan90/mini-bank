import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import Forbidden
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    sub = decode_access_token(token)
    if sub is None:
        raise _unauthorized()
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise _unauthorized() from None
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise Forbidden("Операция доступна только администратору")
    return user
