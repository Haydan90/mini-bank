from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import RegisterRequest, Token, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(db, body.email, body.password)


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Форма OAuth2: поле `username` = email. Так работает кнопка Authorize в /docs."""
    user = auth_service.authenticate(db, form.username, form.password)
    return Token(access_token=create_access_token(str(user.id)))
