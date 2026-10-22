"""Зависимости: текущий пользователь, проверка ролей, шаблоны."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import FRONTEND_DIR
from .db import get_db
from .models import Role, User
from .security import COOKIE_NAME, read_session_token

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "html"))


def _from_json(value, default=()):
    """JSON-строка из БД -> объект Python. from_json / from_json(none)."""
    from .services import loads

    return loads(value, list(default) if default else [])


templates.env.filters["from_json"] = _from_json


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    uid = read_session_token(token)
    if not uid:
        return None
    user = db.get(User, uid)
    if user is None or user.status != "active":
        return None
    return user


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход в систему")
    return user


def require_teacher(user: User = Depends(require_user)) -> User:
    if user.role != Role.teacher.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно только преподавателю")
    return user


def require_student(user: User = Depends(require_user)) -> User:
    if user.role != Role.student.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно только учащемуся")
    return user


def render(request: Request, template: str, user: User | None = None, **context):
    ctx = {"request": request, "user": user}
    ctx.update(context)
    return templates.TemplateResponse(request, template, ctx)
