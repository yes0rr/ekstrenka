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


def _num(value, digits: int = 1) -> str:
    """6.0 -> «6», 4.50 -> «4.5», None -> «—». Убирает хвостовые нули в баллах."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}f}".rstrip("0").rstrip(".")


def _duration(seconds) -> str:
    """0 -> «0 с», 75 -> «1 мин 15 с». Пробел между числом и «с»."""
    try:
        total = int(round(float(seconds or 0)))
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return "0 с"
    minutes, sec = divmod(total, 60)
    return f"{minutes} мин {sec} с" if minutes else f"{sec} с"


def _pct(part, whole) -> str:
    """Доля в процентах целым числом; при whole <= 0 — пустая строка."""
    try:
        part_f, whole_f = float(part or 0), float(whole or 0)
    except (TypeError, ValueError):
        return ""
    if whole_f <= 0:
        return ""
    return f"{round(part_f / whole_f * 100)}%"


templates.env.filters["num"] = _num
templates.env.filters["duration"] = _duration
templates.env.filters["pct"] = _pct


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
    ctx.setdefault("form", {})  # пустая форма по умолчанию: шаблон не упадёт, если её не передали
    ctx.update(context)
    return templates.TemplateResponse(request, template, ctx)
