"""Пароли, сессии (подписанная cookie), логирование действий."""
from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session
from starlette.requests import Request

from .config import settings
from .models import Log

_hasher = PasswordHasher()
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="session")
COOKIE_NAME = "ispytaniya_session"

log_business = logging.getLogger("ispytaniya")


# ---------- пароли ----------
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, Exception):
        return False


# ---------- сессии ----------
def make_session_token(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id, "rnd": secrets.token_hex(4)})


def read_session_token(token: str) -> int | None:
    try:
        data = _serializer.loads(token, max_age=settings.session_max_age)
    except BadSignature:
        return None
    uid = data.get("uid")
    return int(uid) if uid else None


# ---------- логи ----------
def write_log(
    db: Session,
    action: str,
    *,
    request: Request | None = None,
    user_id: int | None = None,
    entity: str | None = None,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    ip = None
    ua = None
    if request is not None:
        forwarded = request.headers.get("x-forwarded-for")
        ip = (forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None))
        ua = (request.headers.get("user-agent") or "")[:300] or None
    db.add(
        Log(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip=ip,
            user_agent=ua,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
    )
    db.commit()
    log_business.info("action=%s user=%s entity=%s/%s", action, user_id, entity, entity_id)
