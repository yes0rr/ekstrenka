"""API видеотеста: разделы → заход → ответы (вариант или свободный текст/голос) → итог.

Одна попытка = одна строка в video_quiz_runs, создаётся при старте:
    POST /start   — какие 10 вопросов достались (случайно) и в каком порядке;
    POST /answer  — ответ на один вопрос (номер варианта или распознанный текст);
    POST /finish  — итог. Повторный вызов возвращает уже сохранённый результат,
                    второй записи в «Прошлых прохождениях» не появляется.

Правильные ответы в браузер не уходят до проверки: считает сервер.
Режимы:
    training — вердикт и пояснение приходят сразу после ответа;
    testing  — вариантов нет, учащийся сам вводит или проговаривает ответ,
               вердикт и разбор — только в конце.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_student
from ..models import Role, User, VideoQuizRun, utcnow
from ..security import write_log
from ..services import dumps, loads
from ..videoquiz import (
    QUESTIONS,
    RUN_SIZE,
    SECTIONS,
    TOTAL,
    by_id,
    pick_questions,
    option_order,
    verdict,
)
from ..voice import choose

router = APIRouter(prefix="/api/video-quiz", tags=["video-quiz"])

ModeName = Literal["training", "testing"]
Lang = Literal["ru", "en"]


class StartIn(BaseModel):
    section: str = "all"
    mode: ModeName = "training"
    lang: Lang = "ru"


class AnswerIn(BaseModel):
    run_id: int = Field(ge=1)
    question_id: int = Field(ge=1)
    answer: int | None = Field(default=None, ge=0, le=10)   # номер варианта на экране
    text: str | None = Field(default=None, max_length=600)  # свободный ответ (зачёт, голос)


class FinishIn(BaseModel):
    run_id: int = Field(ge=1)


class VoiceIn(BaseModel):
    """Расшифровка речи от браузера: находят вариант, но вердикт не раскрывают."""
    run_id: int = Field(ge=1)
    question_id: int = Field(ge=1)
    transcript: str = Field(min_length=1, max_length=600)


def _student(user: User = Depends(require_student)) -> User:
    """Видеотест — для учащихся; преподавателю здесь делать нечего."""
    if user.role != Role.student.value:
        raise HTTPException(403, "Видеотест доступен только учащимся")
    return user


def _own_run(db: Session, run_id: int, user: User) -> VideoQuizRun:
    run = db.get(VideoQuizRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(404, "Попытка не найдена")
    return run


def _orders(run: VideoQuizRun) -> dict[str, list[int]]:
    return loads(run.option_orders, {}) or {}


def _answers(run: VideoQuizRun) -> dict[str, dict]:
    return loads(run.answers, {}) or {}


def _run_questions(run: VideoQuizRun) -> list:
    """Вопросы захода в том порядке, в котором их показывали."""
    found = []
    for qid in loads(run.question_ids, []) or []:
        question = by_id(int(qid))
        if question is not None:
            found.append(question)
    return found


def _public_question(question, order: list[int], lang: str) -> dict:
    options = question.options[lang]
    return {
        "id": question.id,
        "clip": question.clip,
        "title": question.title[lang],
        "question": question.question[lang],
        "options": [options[i] for i in order],
    }


def _resolve(run: VideoQuizRun, question, payload: AnswerIn) -> tuple[int | None, list[str]]:
    """Номер варианта на экране (или None) и совпавшие слова — по номеру либо по тексту."""
    order = _orders(run).get(str(question.id)) or list(range(len(question.options["ru"])))
    if payload.text:
        decision = choose(payload.text, question.voice_options(run.lang))
        original = decision["chosen"]
        if original is None or original not in order:
            return None, decision["matched"]
        return order.index(original), decision["matched"]
    if payload.answer is None:
        return None, []
    if payload.answer >= len(order):
        raise HTTPException(422, "Нет такого варианта ответа")
    return payload.answer, []


@router.get("/sections")
def sections(lang: Lang = "ru", user: User = Depends(_student)) -> dict:
    """Разделы видеотеста: картинка, описание, сколько вопросов."""
    return {"total": TOTAL, "run_size": RUN_SIZE, "items": [s.public(lang) for s in SECTIONS]}


@router.post("/start")
def start(payload: StartIn, db: Session = Depends(get_db),
          user: User = Depends(_student)) -> dict:
    """Новый заход: случайные вопросы раздела и случайный порядок вариантов."""
    picked = pick_questions(payload.section)
    orders = {str(q.id): option_order(q) for q in picked}
    run = VideoQuizRun(
        user_id=user.id,
        section=payload.section,
        mode=payload.mode,
        lang=payload.lang,
        question_ids=dumps([q.id for q in picked]),
        option_orders=dumps(orders),
        answers=dumps({}),
        total=len(picked),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {
        "run_id": run.id,
        "mode": run.mode,
        "lang": run.lang,
        "section": run.section,
        "total": len(picked),
        "items": [_public_question(q, orders[str(q.id)], run.lang) for q in picked],
    }


@router.post("/answer")
def answer(payload: AnswerIn, db: Session = Depends(get_db),
           user: User = Depends(_student)) -> dict:
    """Ответ на один вопрос. Принимает номер варианта или свободный текст (зачёт, голос)."""
    run = _own_run(db, payload.run_id, user)
    if run.finished_at is not None:
        raise HTTPException(409, "Попытка уже завершена")
    question = by_id(payload.question_id)
    run_question_ids = [int(qid) for qid in (loads(run.question_ids, []) or [])]
    if question is None or question.id not in run_question_ids:
        raise HTTPException(404, "Такого вопроса нет в этой попытке")

    order = _orders(run).get(str(question.id)) or list(range(len(question.options["ru"])))
    display_index, matched = _resolve(run, question, payload)

    answers = _answers(run)
    correct = display_index is not None and order[display_index] == question.correct
    answers[str(question.id)] = {
        "display": display_index,
        "text": payload.text,
        "correct": bool(correct),
    }
    run.answers = dumps(answers)
    db.commit()

    if run.mode == "testing":
        # зачёт: подтверждаем приём, но не подсказываем ни вариант, ни вердикт
        return {"question_id": question.id, "accepted": True, "recognised": display_index is not None}

    correct_display = order.index(question.correct)
    return {
        "question_id": question.id,
        "correct": bool(correct),
        "correct_index": correct_display,
        "chosen": display_index,
        "recognised": display_index is not None,
        "matched": matched[:5],
        "explain": question.explain[run.lang],
        "checklist": question.checklist,
    }


@router.post("/voice")
def voice(payload: VoiceIn, db: Session = Depends(get_db),
          user: User = Depends(_student)) -> dict:
    """Голосовой ответ: распознаёт браузер, сервер лишь сопоставляет фразу с вариантом."""
    run = _own_run(db, payload.run_id, user)
    question = by_id(payload.question_id)
    run_question_ids = [int(qid) for qid in (loads(run.question_ids, []) or [])]
    if question is None or question.id not in run_question_ids:
        raise HTTPException(404, "Такого вопроса нет в этой попытке")

    decision = choose(payload.transcript, question.voice_options(run.lang))
    order = _orders(run).get(str(question.id)) or list(range(len(question.options["ru"])))
    display = order.index(decision["chosen"]) if decision["chosen"] in order else None
    return {
        "question_id": question.id,
        "chosen": display,
        "option_text": question.options[run.lang][decision["chosen"]]
        if decision["chosen"] is not None else None,
        "confidence": decision["confidence"],
        "matched": decision["matched"][:5],
        "transcript": decision["transcript"],
        "ambiguous": bool(decision.get("ambiguous")),
        "mode": run.mode,
    }


def _summary(run: VideoQuizRun) -> dict:
    """Итог попытки: считается из сохранённых ответов (одинаково при повторном запросе)."""
    lang = run.lang
    orders = _orders(run)
    answers = _answers(run)
    details = []
    score = 0
    questions = _run_questions(run)
    for question in questions:
        order = orders.get(str(question.id)) or list(range(len(question.options["ru"])))
        stored = answers.get(str(question.id)) or {}
        display = stored.get("display")
        correct_index = order.index(question.correct)
        correct = display is not None and display == correct_index
        score += int(correct)
        details.append({
            "id": question.id,
            "title": question.title[lang],
            "question": question.question[lang],
            "options": [question.options[lang][i] for i in order],
            "chosen": display if display is not None else -1,
            "text": stored.get("text"),
            "correct": correct,
            "correct_index": correct_index,
            "explain": question.explain[lang],
            "checklist": question.checklist,
        })

    total = len(questions) or run.total or 1
    percent = round(score * 100 / total, 1)
    code, text = verdict(percent, lang)
    return {
        "id": run.id,
        "score": score,
        "total": total,
        "percent": percent,
        "verdict": code,
        "verdict_text": text,
        "mode": run.mode,
        "section": run.section,
        "lang": lang,
        "details": details,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.post("/finish")
def finish(payload: FinishIn, db: Session = Depends(get_db),
           user: User = Depends(_student)) -> dict:
    """Завершить попытку. Повторное нажатие ничего не пишет — отдаёт тот же результат."""
    run = _own_run(db, payload.run_id, user)
    already = run.finished_at is not None
    summary = _summary(run)

    if not already:
        run.score = summary["score"]
        run.percent = summary["percent"]
        run.total = summary["total"]
        run.finished_at = utcnow()
        db.commit()
        db.refresh(run)
        summary["finished_at"] = run.finished_at.isoformat() if run.finished_at else None
        write_log(db, "video_quiz_finished", user_id=user.id,
                  entity="video_quiz_run", entity_id=run.id,
                  payload={"score": run.score, "total": run.total,
                           "percent": run.percent, "mode": run.mode,
                           "section": run.section})
    summary["already_finished"] = already
    return summary


@router.get("/results")
def results(db: Session = Depends(get_db), user: User = Depends(_student)) -> dict:
    """История: только завершённые попытки, по одной строке на заход."""
    rows = db.scalars(
        select(VideoQuizRun)
        .where(VideoQuizRun.user_id == user.id, VideoQuizRun.finished_at.is_not(None))
        .order_by(VideoQuizRun.finished_at.desc())
        .limit(10)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "score": row.score,
                "total": row.total,
                "percent": row.percent,
                "mode": row.mode,
                "section": row.section,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ]
    }


@router.get("/results/{run_id}")
def result_detail(run_id: int, db: Session = Depends(get_db),
                  user: User = Depends(_student)) -> dict:
    """Разбор завершённой попытки: что было выбрано и как правильно."""
    run = _own_run(db, run_id, user)
    if run.finished_at is None:
        raise HTTPException(404, "Попытка не завершена")
    return _summary(run)
