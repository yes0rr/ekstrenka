"""API видеотеста: вопросы → проверка ответа → итог и разбор → история.

Правильные ответы не уходят в браузер до проверки: клиент присылает только
номер выбранного варианта, вердикт считает сервер.

Режимы:
    training — вердикт по каждому вопросу приходит сразу (обучение);
    testing  — ответ только принимается, вердикт и разбор — в конце (зачёт).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_student
from ..models import Role, User, VideoQuizResult
from ..security import write_log
from ..services import dumps, loads
from ..videoquiz import QUESTIONS, TOTAL, by_id, check, verdict
from ..voice import choose

router = APIRouter(prefix="/api/video-quiz", tags=["video-quiz"])

ModeName = Literal["training", "testing"]
Lang = Literal["ru", "en"]


class AnswerIn(BaseModel):
    question_id: int = Field(ge=1)
    answer: int = Field(ge=0, le=10)
    mode: ModeName = "training"
    lang: Lang = "ru"


class FinishIn(BaseModel):
    answers: dict[int, int] = Field(default_factory=dict)
    mode: ModeName = "training"
    lang: Lang = "ru"


class VoiceIn(BaseModel):
    """Расшифровка речи от браузера (Web Speech API)."""
    question_id: int = Field(ge=1)
    transcript: str = Field(min_length=1, max_length=600)
    lang: Lang = "ru"


def _student(user: User = Depends(require_student)) -> User:
    """Видеотест — для учащихся; преподавателю здесь делать нечего."""
    if user.role != Role.student.value:
        raise HTTPException(403, "Видеотест доступен только учащимся")
    return user


@router.get("/questions")
def questions(lang: Lang = "ru", user: User = Depends(_student)) -> dict:
    """Список фрагментов и вопросов без правильных ответов (язык — параметром lang)."""
    return {
        "total": TOTAL,
        "lang": lang,
        "items": [q.public(lang) for q in QUESTIONS],
    }


@router.post("/answer")
def answer(payload: AnswerIn, user: User = Depends(_student)) -> dict:
    """Проверка одного ответа. В режиме зачёта вердикт не раскрывается."""
    question = by_id(payload.question_id)
    if question is None:
        raise HTTPException(404, "Такого вопроса нет")
    if payload.answer >= len(question.options):
        raise HTTPException(422, "Нет такого варианта ответа")

    result = check(question, payload.answer, payload.lang)
    if payload.mode == "testing":
        # зачёт: подтверждаем приём, но не подсказываем
        return {"question_id": question.id, "accepted": True}
    return result


@router.post("/voice")
def voice(payload: VoiceIn, user: User = Depends(_student)) -> dict:
    """Голосовой ответ: расшифровка речи → номер варианта.

    Распознаёт речь браузер, сервер только сопоставляет фразу с вариантами по словам-подсказкам.
    Возвращает номер варианта и уверенность; проверку ответа делает /answer.
    """
    question = by_id(payload.question_id)
    if question is None:
        raise HTTPException(404, "Такого вопроса нет")

    triggers = question.voice_options(payload.lang)
    if not triggers:
        raise HTTPException(422, "Для этого вопроса нет голосовых подсказок")

    decision = choose(payload.transcript, triggers)
    index = decision["chosen"]
    return {
        "question_id": question.id,
        "chosen": index,
        "option_text": question.options[payload.lang][index] if index is not None else None,
        "confidence": decision["confidence"],
        "matched": decision["matched"][:5],
        "transcript": decision["transcript"],
        "ambiguous": bool(decision.get("ambiguous")),
    }


@router.post("/finish")
def finish(payload: FinishIn, db: Session = Depends(get_db),
           user: User = Depends(_student)) -> dict:
    """Итог прохождения: считаем балл, сохраняем в БД, отдаём разбор."""
    if not payload.answers:
        raise HTTPException(422, "Нет ответов")

    details = []
    score = 0
    for question in QUESTIONS:
        chosen = payload.answers.get(question.id)
        if chosen is None:
            correct = False
            chosen = -1
        else:
            correct = chosen == question.correct
        score += int(correct)
        details.append({
            "id": question.id,
            "title": question.title[payload.lang],
            "question": question.question[payload.lang],
            "options": list(question.options[payload.lang]),
            "chosen": chosen,
            "correct": correct,
            "correct_index": question.correct,
            "explain": question.explain[payload.lang],
            "checklist": question.checklist,
        })

    percent = round(score * 100 / TOTAL, 1)
    code, text = verdict(percent, payload.lang)

    row = VideoQuizResult(
        user_id=user.id,
        score=score,
        total=TOTAL,
        percent=percent,
        details=dumps({"mode": payload.mode, "lang": payload.lang, "items": details}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_log(db, "video_quiz_finished", user_id=user.id,
              entity="video_quiz_result", entity_id=row.id,
              payload={"score": score, "total": TOTAL, "percent": percent, "mode": payload.mode})

    return {
        "id": row.id,
        "score": score,
        "total": TOTAL,
        "percent": percent,
        "verdict": code,
        "verdict_text": text,
        "details": details,
    }


@router.get("/results")
def results(db: Session = Depends(get_db), user: User = Depends(_student)) -> dict:
    """История прохождений учащегося — последние 10."""
    rows = db.scalars(
        select(VideoQuizResult)
        .where(VideoQuizResult.user_id == user.id)
        .order_by(VideoQuizResult.created_at.desc())
        .limit(10)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "score": row.score,
                "total": row.total,
                "percent": row.percent,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.get("/results/{result_id}")
def result_detail(result_id: int, lang: Lang = "ru", db: Session = Depends(get_db),
                  user: User = Depends(_student)) -> dict:
    """Разбор прошлого прохождения: что было выбрано и как правильно."""
    row = db.get(VideoQuizResult, result_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Прохождение не найдено")
    payload = loads(row.details, {}) or {}
    code, text = verdict(row.percent, lang)
    return {
        "id": row.id,
        "score": row.score,
        "total": row.total,
        "percent": row.percent,
        "verdict": code,
        "verdict_text": text,
        "mode": payload.get("mode", "training"),
        "details": payload.get("items", []) if payload.get("lang", "ru") == lang
                   else [q.public(lang) | {"correct_index": None} for q in QUESTIONS],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
