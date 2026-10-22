"""Страницы и эндпоинты авторизации/регистрации."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, render, require_user
from ..models import Role, User, utcnow
from ..security import COOKIE_NAME, hash_password, make_session_token, verify_password, write_log


def _set_session_cookie(response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_session_token(user_id),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_max_age,
    )

router = APIRouter(tags=["auth"])


# ----------------------------- страницы -----------------------------
@router.get("/login")
def login_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", error=None)


@router.post("/login")
def login_form(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(user.password_hash, password):
        write_log(db, "login_failed", request=request, payload={"email": email})
        return render(request, "login.html", error="Неверная почта или пароль")
    if user.status != "active":
        return render(request, "login.html", error="Аккаунт заблокирован")

    user.last_login_at = utcnow()
    db.commit()
    write_log(db, "login", request=request, user_id=user.id)

    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, user.id)
    return response


@router.get("/register")
def register_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return render(request, "register.html", error=None, allow_teacher_signup=settings.allow_teacher_signup)


@router.post("/register")
def register_form(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("student"),
    group_name: str = Form(""),
):
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        return render(request, "register.html", error="Пользователь с такой почтой уже есть", allow_teacher_signup=settings.allow_teacher_signup)
    if len(password) < 6:
        return render(request, "register.html", error="Пароль должен быть не короче 6 символов", allow_teacher_signup=settings.allow_teacher_signup)

    if not settings.allow_teacher_signup:
        role = Role.student.value

    user = User(
        email=email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role if role in {r.value for r in Role} else Role.student.value,
        group_name=group_name.strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_log(db, "register", request=request, user_id=user.id, payload={"role": user.role})

    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, user.id)
    return response


@router.post("/logout")
def logout_form(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if user:
        write_log(db, "logout", request=request, user_id=user.id)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ----------------------------- API -----------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: str = "student"
    group_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/api/auth/register")
def api_register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        return JSONResponse({"detail": "Пользователь с такой почтой уже есть"}, status_code=409)
    role = payload.role if payload.role in {r.value for r in Role} else Role.student.value
    if not settings.allow_teacher_signup:
        role = Role.student.value
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=role,
        group_name=payload.group_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_log(db, "register", request=request, user_id=user.id, payload={"via": "api"})
    _set_session_cookie(response, user.id)
    return {"id": user.id, "email": user.email, "role": user.role, "full_name": user.full_name}


@router.post("/api/auth/login")
def api_login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(user.password_hash, payload.password):
        write_log(db, "login_failed", request=request, payload={"email": payload.email, "via": "api"})
        return JSONResponse({"detail": "Неверная почта или пароль"}, status_code=401)
    if user.status != "active":
        return JSONResponse({"detail": "Аккаунт заблокирован"}, status_code=403)
    user.last_login_at = utcnow()
    db.commit()
    write_log(db, "login", request=request, user_id=user.id, payload={"via": "api"})
    token = make_session_token(user.id)
    _set_session_cookie(response, user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "full_name": user.full_name}}


@router.post("/api/auth/logout")
def api_logout(request: Request, response: Response, db: Session = Depends(get_db),
               user: User | None = Depends(get_current_user)):
    if user:
        write_log(db, "logout", request=request, user_id=user.id, payload={"via": "api"})
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/api/me")
def api_me(user: User | None = Depends(get_current_user)):
    if not user:
        return JSONResponse({"detail": "Не авторизован"}, status_code=401)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "group_name": user.group_name,
    }


# ----------------------------- аккаунт -----------------------------
@router.get("/account")
def account_page(request: Request, user: User | None = Depends(get_current_user)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return render(request, "account.html", user, error=None, ok=None)


@router.post("/account/profile")
def account_profile(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    full_name: str = Form(...),
    group_name: str = Form(""),
):
    user.full_name = full_name.strip()[:255]
    user.group_name = group_name.strip() or None
    db.commit()
    write_log(db, "profile_updated", request=request, user_id=user.id)
    return render(request, "account.html", user, error=None, ok="Профиль обновлён")


@router.post("/account/password")
def account_password(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
):
    if not verify_password(user.password_hash, current_password):
        return render(request, "account.html", user, error="Текущий пароль неверный", ok=None)
    if len(new_password) < 8:
        return render(request, "account.html", user, error="Новый пароль — минимум 8 символов", ok=None)
    if new_password != new_password2:
        return render(request, "account.html", user, error="Пароли не совпадают", ok=None)
    user.password_hash = hash_password(new_password)
    db.commit()
    write_log(db, "password_changed", request=request, user_id=user.id)
    return render(request, "account.html", user, error=None, ok="Пароль изменён")
