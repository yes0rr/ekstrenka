"""Эндпоинты видеоанализа: очередь, приём кадров, итог.

Логика станции:
    1. POST /vision/join   — встать в очередь (или сразу получить слот);
    2. GET  /vision/status — «вы 2-й в очереди, ждать ~2 мин» / живые показатели;
    3. POST /frames        — по кадру 15 раз в секунду, пока идёт станция;
    4. POST /vision/leave  — закончить, получить итоговые показатели.

Кадры НЕ сохраняются: JPEG декодируется в памяти воркера и выбрасывается.
В базу уходят только числа (темп, глубина, проценты по критериям).
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import Attempt, Role, User
from ..services import loads
from ..vision import QueueFullError, VisionDisabledError, get_service

router = APIRouter(prefix="/api", tags=["vision"])


class FrameIn(BaseModel):
    image: str = Field(min_length=32, description="data:image/jpeg;base64,... или просто base64")
    ts_ms: int | None = Field(default=None, description="метка времени кадра, мс")


def _own_attempt(db: Session, attempt_id: int, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(404, "Попытка не найдена")
    if user.role == Role.student.value and attempt.student_id != user.id:
        raise HTTPException(403, "Это не ваша попытка")
    return attempt


@router.post("/attempts/{attempt_id}/vision/join")
def vision_join(attempt_id: int, db: Session = Depends(get_db),
                user: User = Depends(require_user)) -> dict[str, Any]:
    """Встать в очередь видеоанализа. Повторный вызов возвращает текущий статус."""
    attempt = _own_attempt(db, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(409, "Попытка уже завершена")
    try:
        info = get_service().join(attempt_id)
    except VisionDisabledError as exc:
        raise HTTPException(503, str(exc)) from exc
    except QueueFullError as exc:
        raise HTTPException(429, str(exc)) from exc
    return info


@router.get("/attempts/{attempt_id}/vision/status")
def vision_status(attempt_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_user)) -> dict[str, Any]:
    """Позиция в очереди и живые показатели техники (обновляется по ходу станции)."""
    _own_attempt(db, attempt_id, user)
    info = get_service().status(attempt_id)
    if info is None:
        # сессии нет — показывает сохранённый ранее результат, если он есть
        attempt = db.get(Attempt, attempt_id)
        return {
            "status": attempt.vision_status if attempt else "off",
            "saved": loads(attempt.vision_data, None) if attempt else None,
        }
    return info


@router.post("/attempts/{attempt_id}/frames")
def push_frame(attempt_id: int, payload: FrameIn, request: Request,
               db: Session = Depends(get_db), user: User = Depends(require_user)) -> dict[str, Any]:
    """Один кадр → метрики. Вызывается 15 раз в секунду с фронта."""
    attempt = _own_attempt(db, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(409, "Попытка уже завершена")
    try:
        return get_service().push_frame(attempt_id, payload.image, payload.ts_ms)
    except VisionDisabledError as exc:
        raise HTTPException(503, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(409, exc.args[0] if exc.args else "сессия не открыта") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/attempts/{attempt_id}/vision/leave")
def vision_leave(attempt_id: int, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require_user)) -> dict[str, Any]:
    """Завершить видеоанализ и сохранить итог в попытку."""
    attempt = _own_attempt(db, attempt_id, user)
    summary = get_service().leave(attempt_id)
    if summary is not None:
        from ..security import write_log

        get_service().persist(attempt, summary)
        db.commit()
        write_log(db, "vision_finished", request=request, user_id=user.id,
                  entity="attempt", entity_id=attempt.id,
                  payload={"tempo_bpm": summary.get("tempo_bpm"),
                           "depth_cm": summary.get("depth_cm"),
                           "frames": summary.get("frames_total")})
    return {"saved": summary is not None, "result": summary,
            "stored": loads(attempt.vision_data, None)}


@router.get("/vision/stats")
def vision_stats(user: User = Depends(require_user)) -> dict[str, Any]:
    """Диагностика для преподавателя: сколько слотов, живой ли воркер, сколько кадров отброшено."""
    from ..models import Role as _Role

    data = get_service().stats()
    if user.role != _Role.teacher.value:
        data.pop("error", None)
    return data


# использовать «сейчас» из одного места, чтобы метки времени были согласованы
def _now_ms() -> int:
    return int(time.monotonic() * 1000)
