"""JSON API: испытания, вопросы, попытки, ответы, медиа, оценки, логи.

Сюда стучится фронтенд («запросы от сайта»), сюда же можно бить извне.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import get_current_user, require_teacher, require_user
from ..models import (
    Answer,
    Attempt,
    AttemptStatus,
    Log,
    Mode,
    Question,
    Role,
    SubjectType,
    Test,
    User,
    utcnow,
)
from ..neural import evaluate_attempt
from ..security import write_log
from ..services import check_answer, dumps, loads, recompute_score

router = APIRouter(prefix="/api", tags=["api"])


# ----------------------------- схемы -----------------------------
class TestIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = None
    mode: Literal["training", "testing"] = "testing"
    subject_type: Literal["human", "imitation"] = "human"
    duration_min: int = Field(default=15, ge=1, le=600)
    use_camera: bool = True
    use_mic: bool = True
    criteria: str | None = None


class TestPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    mode: Literal["training", "testing"] | None = None
    subject_type: Literal["human", "imitation"] | None = None
    duration_min: int | None = Field(default=None, ge=1, le=600)
    use_camera: bool | None = None
    use_mic: bool | None = None
    criteria: str | None = None
    is_published: bool | None = None


class QuestionIn(BaseModel):
    text: str = Field(min_length=1)
    kind: Literal["single", "multiple", "text", "text_manual"] = "single"
    options: list[str] = Field(default_factory=list)
    correct: list[str] | str | None = None
    points: float = Field(default=1.0, ge=0, le=100)
    hint: str | None = None


class AttemptIn(BaseModel):
    test_id: int
    subject_type: Literal["human", "imitation"] | None = None


class AnswerIn(BaseModel):
    question_id: int
    value: Any = None


class MediaIn(BaseModel):
    camera: bool = False
    mic: bool = False
    seconds: int = 0
    note: str | None = None


class ManualResultIn(BaseModel):
    manual_score: float = Field(ge=0)
    teacher_comment: str | None = None


# ----------------------------- helpers -----------------------------
def _test_dict(test: Test, *, with_questions: bool = False, for_student: bool = False,
               show_correct: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": test.id,
        "title": test.title,
        "description": test.description,
        "mode": test.mode,
        "subject_type": test.subject_type,
        "duration_min": test.duration_min,
        "use_camera": test.use_camera,
        "use_mic": test.use_mic,
        "criteria": test.criteria,
        "is_published": test.is_published,
        "author": test.author.full_name if test.author else None,
        "created_at": test.created_at.isoformat(),
        "questions_count": len(test.questions),
        "max_score": test.max_score,
    }
    if with_questions:
        items = []
        for q in test.questions:
            item = {
                "id": q.id,
                "order_index": q.order_index,
                "text": q.text,
                "kind": q.kind,
                "options": loads(q.options, []),
                "points": q.points,
            }
            if not for_student or show_correct:
                item["correct"] = loads(q.correct, None)
                item["hint"] = q.hint
            items.append(item)
        data["questions"] = items
    return data


def _attempt_dict(attempt: Attempt, *, include_answers: bool = False, for_student: bool = False) -> dict[str, Any]:
    data = {
        "id": attempt.id,
        "test_id": attempt.test_id,
        "test_title": attempt.test.title if attempt.test else None,
        "student_id": attempt.student_id,
        "student_name": attempt.student.full_name if attempt.student else None,
        "status": attempt.status,
        "mode": attempt.mode,
        "subject_type": attempt.subject_type,
        "started_at": attempt.started_at.isoformat(),
        "finished_at": attempt.finished_at.isoformat() if attempt.finished_at else None,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "manual_score": attempt.manual_score,
        "final_score": attempt.final_score,
        "teacher_comment": attempt.teacher_comment,
        "neural_status": attempt.neural_status,
        "neural_score": attempt.neural_score,
        "neural_comment": attempt.neural_comment,
        "vision_status": attempt.vision_status,
        "vision": loads(attempt.vision_data, None),
        "media": {
            "camera": attempt.camera_used,
            "mic": attempt.mic_used,
            "seconds": attempt.media_seconds,
            "note": attempt.media_note,
        },
    }
    if include_answers:
        data["answers"] = [
            {
                "question_id": a.question_id,
                "question": a.question.text if a.question else None,
                "value": loads(a.value, None),
                "is_correct": a.is_correct,
                "awarded_points": a.awarded_points,
                "is_manual": a.is_manual,
            }
            for a in attempt.answers
        ]
    return data


def _get_test(db: Session, test_id: int) -> Test:
    test = db.scalar(
        select(Test).options(selectinload(Test.questions)).where(Test.id == test_id)
    )
    if not test:
        raise HTTPException(404, "Испытание не найдено")
    return test


def _get_attempt(db: Session, attempt_id: int) -> Attempt:
    attempt = db.scalar(
        select(Attempt)
        .options(
            selectinload(Attempt.answers).selectinload(Answer.question),
            selectinload(Attempt.test).selectinload(Test.questions),
            selectinload(Attempt.student),
        )
        .where(Attempt.id == attempt_id)
        .execution_options(populate_existing=True)
    )
    if not attempt:
        raise HTTPException(404, "Попытка не найдена")
    return attempt


# ----------------------------- испытания -----------------------------
@router.get("/tests")
def list_tests(db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(401, "Требуется вход")
    stmt = select(Test).options(selectinload(Test.questions), selectinload(Test.author))
    if user.role == Role.teacher.value:
        stmt = stmt.where(Test.author_id == user.id)
    else:
        stmt = stmt.where(Test.is_published.is_(True))
    tests = db.scalars(stmt.order_by(Test.created_at.desc())).all()
    return [_test_dict(t, for_student=user.role == Role.student.value) for t in tests]


@router.post("/tests", status_code=201)
def create_test(payload: TestIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    test = Test(author_id=user.id, **payload.model_dump())
    db.add(test)
    db.commit()
    db.refresh(test)
    write_log(db, "test_created", request=request, user_id=user.id, entity="test", entity_id=test.id,
              payload={"title": test.title, "mode": test.mode})
    return _test_dict(test)


@router.get("/tests/{test_id}")
def get_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    test = _get_test(db, test_id)
    is_student = user.role == Role.student.value
    if is_student and not test.is_published:
        raise HTTPException(403, "Испытание не опубликовано")
    # в режиме обучения учащийся видит правильные ответы и подсказки
    show_correct = is_student and test.mode == Mode.training.value
    return _test_dict(test, with_questions=True, for_student=is_student, show_correct=show_correct)


@router.patch("/tests/{test_id}")
def patch_test(test_id: int, payload: TestPatch, request: Request, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    test = _get_test(db, test_id)
    if test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(test, key, value)
    db.commit()
    write_log(db, "test_updated", request=request, user_id=user.id, entity="test", entity_id=test.id,
              payload=changes)
    return _test_dict(test, with_questions=True)


@router.delete("/tests/{test_id}", status_code=204)
def delete_test(test_id: int, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    test = _get_test(db, test_id)
    if test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    db.delete(test)
    db.commit()
    write_log(db, "test_deleted", request=request, user_id=user.id, entity="test", entity_id=test_id)


# ----------------------------- вопросы -----------------------------
@router.post("/tests/{test_id}/questions", status_code=201)
def add_question(test_id: int, payload: QuestionIn, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    test = _get_test(db, test_id)
    if test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    question = Question(
        test_id=test.id,
        order_index=len(test.questions),
        text=payload.text,
        kind=payload.kind,
        options=dumps(payload.options or []),
        correct=dumps(payload.correct) if payload.correct is not None else None,
        points=payload.points,
        hint=payload.hint,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    write_log(db, "question_added", request=request, user_id=user.id, entity="question", entity_id=question.id)
    return {"id": question.id, "order_index": question.order_index}


@router.patch("/questions/{question_id}")
def patch_question(question_id: int, payload: QuestionIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require_teacher)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Вопрос не найден")
    if question.test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    question.text = payload.text
    question.kind = payload.kind
    question.options = dumps(payload.options or [])
    question.correct = dumps(payload.correct) if payload.correct is not None else None
    question.points = payload.points
    question.hint = payload.hint
    db.commit()
    write_log(db, "question_updated", request=request, user_id=user.id, entity="question", entity_id=question_id)
    return {"ok": True}


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(require_teacher)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Вопрос не найден")
    if question.test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    db.delete(question)
    db.commit()
    write_log(db, "question_deleted", request=request, user_id=user.id, entity="question", entity_id=question_id)


# ----------------------------- попытки -----------------------------
@router.post("/attempts", status_code=201)
def start_attempt(payload: AttemptIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_user)):
    test = _get_test(db, payload.test_id)
    if not test.is_published:
        raise HTTPException(403, "Испытание не опубликовано")
    if not test.questions:
        raise HTTPException(400, "В испытании нет вопросов")

    open_attempt = db.scalar(
        select(Attempt).where(
            Attempt.test_id == test.id,
            Attempt.student_id == user.id,
            Attempt.status == AttemptStatus.in_progress.value,
        )
    )
    if open_attempt:
        return _attempt_dict(open_attempt)

    attempt = Attempt(
        test_id=test.id,
        student_id=user.id,
        mode=test.mode,
        subject_type=payload.subject_type or test.subject_type,
        max_score=test.max_score,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    write_log(db, "attempt_started", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id,
              payload={"test_id": test.id, "mode": test.mode})
    return _attempt_dict(attempt)


@router.get("/attempts")
def list_attempts(test_id: int | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require_user)):
    stmt = select(Attempt).options(
        selectinload(Attempt.test), selectinload(Attempt.student)
    )
    if user.role == Role.teacher.value:
        stmt = stmt.join(Test).where(Test.author_id == user.id)
    else:
        stmt = stmt.where(Attempt.student_id == user.id)
    if test_id:
        stmt = stmt.where(Attempt.test_id == test_id)
    attempts = db.scalars(stmt.order_by(Attempt.started_at.desc())).all()
    return [_attempt_dict(a) for a in attempts]


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    attempt = _get_attempt(db, attempt_id)
    if user.role == Role.student.value and attempt.student_id != user.id:
        raise HTTPException(403, "Это не ваша попытка")
    return _attempt_dict(attempt, include_answers=True)


@router.post("/attempts/{attempt_id}/answers")
def save_answer(attempt_id: int, payload: AnswerIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_user)):
    attempt = _get_attempt(db, attempt_id)
    if attempt.student_id != user.id:
        raise HTTPException(403, "Это не ваша попытка")
    if attempt.status != AttemptStatus.in_progress.value:
        raise HTTPException(409, "Попытка уже завершена")

    question = db.get(Question, payload.question_id)
    if not question or question.test_id != attempt.test_id:
        raise HTTPException(404, "Вопрос не относится к этому испытанию")

    is_correct, awarded = check_answer(question, payload.value)
    # в режиме тестирования вердикт по ходу не раскрываем
    hide_verdict = attempt.mode == Mode.testing.value

    answer = db.scalar(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    )
    if answer is None:
        answer = Answer(attempt_id=attempt.id, question_id=question.id)
        db.add(answer)
    answer.value = dumps(payload.value)
    answer.is_correct = is_correct
    answer.awarded_points = awarded
    db.commit()

    attempt = _get_attempt(db, attempt_id)
    recompute_score(attempt)
    db.commit()

    result: dict[str, Any] = {"saved": True, "progress": len(attempt.answers)}
    if not hide_verdict:
        result.update(
            {
                "is_correct": is_correct,
                "awarded_points": awarded,
                "correct": loads(question.correct, None),
                "hint": question.hint,
                "comment": "Верно" if is_correct else ("Проверит преподаватель" if is_correct is None else "Неверно"),
            }
        )
    write_log(db, "answer_saved", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id,
              payload={"question_id": question.id})
    return result


@router.post("/attempts/{attempt_id}/media")
def save_media(attempt_id: int, payload: MediaIn, request: Request, db: Session = Depends(get_db),
               user: User = Depends(require_user)):
    """Метаданные камеры/микрофона. Файлы пока не сохраняются — заглушка."""
    attempt = _get_attempt(db, attempt_id)
    if attempt.student_id != user.id:
        raise HTTPException(403, "Это не ваша попытка")
    attempt.camera_used = payload.camera
    attempt.mic_used = payload.mic
    attempt.media_seconds = max(attempt.media_seconds, payload.seconds)
    attempt.media_note = payload.note
    db.commit()
    write_log(db, "media_meta", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id,
              payload={"camera": payload.camera, "mic": payload.mic, "seconds": payload.seconds})
    return {"ok": True, "saved_seconds": attempt.media_seconds}


@router.post("/attempts/{attempt_id}/finish")
async def finish_attempt(attempt_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require_user)):
    attempt = _get_attempt(db, attempt_id)
    if attempt.student_id != user.id and user.role != Role.teacher.value:
        raise HTTPException(403, "Недостаточно прав")
    if attempt.status == AttemptStatus.finished.value:
        return _attempt_dict(attempt, include_answers=True)

    recompute_score(attempt)
    attempt.status = AttemptStatus.finished.value
    attempt.finished_at = utcnow()
    db.commit()

    # если видеоанализ ещё идёт — закрываем его и сохраняем итог
    from ..vision import get_service as _get_vision

    vision_summary = _get_vision().leave(attempt.id)
    if vision_summary is not None:
        _get_vision().persist(attempt, vision_summary)
        db.commit()

    payload = {
        "attempt_id": attempt.id,
        "test_title": attempt.test.title,
        "criteria": attempt.test.criteria,
        "mode": attempt.mode,
        "subject_type": attempt.subject_type,
        "answers": [
            {
                "question": a.question.text if a.question else "",
                "answer": str(loads(a.value, a.value)),
                "is_correct": a.is_correct,
            }
            for a in attempt.answers
        ],
        "media": {"camera": attempt.camera_used, "mic": attempt.mic_used, "seconds": attempt.media_seconds},
        "vision": loads(attempt.vision_data, None),
    }
    verdict = await evaluate_attempt(payload)
    attempt.neural_status = verdict.get("status", "pending")
    attempt.neural_score = verdict.get("score")
    attempt.neural_comment = verdict.get("comment")
    db.commit()

    write_log(db, "attempt_finished", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id,
              payload={"score": attempt.score, "max_score": attempt.max_score})
    return _attempt_dict(attempt, include_answers=True)


@router.post("/attempts/{attempt_id}/abort")
def abort_attempt(attempt_id: int, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_user)):
    attempt = _get_attempt(db, attempt_id)
    if attempt.student_id != user.id and user.role != Role.teacher.value:
        raise HTTPException(403, "Недостаточно прав")
    if attempt.status == AttemptStatus.in_progress.value:
        attempt.status = AttemptStatus.aborted.value
        attempt.finished_at = utcnow()
        db.commit()
        write_log(db, "attempt_aborted", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id)
    return {"ok": True, "status": attempt.status}


@router.post("/attempts/{attempt_id}/manual-result")
def manual_result(attempt_id: int, payload: ManualResultIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    """Ручной ввод оценки преподавателем — перекрывает автооценку."""
    attempt = _get_attempt(db, attempt_id)
    if attempt.test.author_id != user.id:
        raise HTTPException(403, "Это не ваше испытание")
    if payload.manual_score > (attempt.max_score or 0):
        raise HTTPException(400, f"Балл не может быть больше максимума ({attempt.max_score})")
    attempt.manual_score = payload.manual_score
    attempt.teacher_comment = payload.teacher_comment
    db.commit()
    write_log(db, "manual_result", request=request, user_id=user.id, entity="attempt", entity_id=attempt.id,
              payload={"manual_score": payload.manual_score})
    return _attempt_dict(attempt, include_answers=True)


# ----------------------------- логи и пользователи -----------------------------
@router.get("/logs")
def list_logs(limit: int = 100, action: str | None = None, db: Session = Depends(get_db),
              user: User = Depends(require_teacher)):
    stmt = select(Log).options(selectinload(Log.user)).order_by(Log.created_at.desc()).limit(min(limit, 500))
    if action:
        stmt = stmt.where(Log.action == action)
    return [
        {
            "id": log.id,
            "action": log.action,
            "user": log.user.full_name if log.user else None,
            "user_id": log.user_id,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "ip": log.ip,
            "payload": loads(log.payload, None),
            "created_at": log.created_at.isoformat(),
        }
        for log in db.scalars(stmt).all()
    ]


@router.get("/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "status": u.status,
            "group_name": u.group_name,
            "created_at": u.created_at.isoformat(),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


class UserPatch(BaseModel):
    role: Literal["teacher", "student"] | None = None
    status: Literal["active", "blocked"] | None = None
    group_name: str | None = None


@router.patch("/users/{user_id}")
def patch_user(user_id: int, payload: UserPatch, request: Request, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    changes = payload.model_dump(exclude_unset=True)
    if target.id == user.id and changes.get("role") == "student":
        raise HTTPException(400, "Нельзя снять роль с самого себя")
    for key, value in changes.items():
        setattr(target, key, value)
    db.commit()
    write_log(db, "user_updated", request=request, user_id=user.id, entity="user", entity_id=target.id,
              payload=changes)
    return {"ok": True}
