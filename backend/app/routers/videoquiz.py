"""API видеотеста «Экстренка»: разделы → тест → ответы словами → итог.

Новая структура (v24): два раздела — «Диагностика» и «Лечение», в каждом
девять тестов по сценариям станции и один общий тест по всем вопросам.
Вариантов ответа нет: учащийся пишет или проговаривает ответ, сервер сравнивает
его с эталоном по смыслу (backend/app/answermatch.py).

Одна попытка = одна строка в video_quiz_runs (поле section хранит ключ теста):
    POST /start   — вопросы теста в случайном порядке;
    POST /answer  — ответ на один вопрос (текст или распознанная речь);
    POST /finish  — итог. Повторный вызов отдаёт уже сохранённый результат.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_student, require_user
from ..models import Role, User, VideoQuizRun, utcnow
from ..security import write_log
from ..services import dumps, loads
from ..videoquiz import (
    SECTION_BY_KEY,
    SECTIONS,
    TEST_BY_KEY,
    TESTS,
    TOTAL,
    by_id,
    by_test,
    check,
    pick_questions,
    section_tests,
    verdict,
)
from .. import quizedit, speech
from ..answermatch import match

router = APIRouter(prefix="/api/video-quiz", tags=["video-quiz"])

ModeName = Literal["training", "testing"]
Lang = Literal["ru", "en"]


class StartIn(BaseModel):
    test: str = "diagnostics_all"     # ключ теста; неизвестный — ошибка
    mode: ModeName = "training"
    lang: Lang = "ru"


class AnswerIn(BaseModel):
    run_id: int = Field(ge=1)
    question_id: int = Field(ge=1)
    text: str | None = Field(default=None, max_length=600)


class FinishIn(BaseModel):
    run_id: int = Field(ge=1)


class TranscribeIn(BaseModel):
    """Короткая запись с микрофона (webm/opus, wav, mp4) в base64 — распознаём на сервере."""
    audio: str = Field(default="", description="data:audio/webm;base64,... или просто base64")
    lang: Lang = "ru"


class VoiceIn(BaseModel):
    """Расшифровка речи от браузера: показываем, что услышали, но не вердикт."""
    run_id: int = Field(ge=1)
    question_id: int = Field(ge=1)
    transcript: str = Field(min_length=1, max_length=600)


def _student(user: User = Depends(require_user)) -> User:
    """Видеотест: учащийся проходит, преподаватель — проверяет (тот же интерфейс)."""
    if user.role not in (Role.student.value, Role.teacher.value):
        raise HTTPException(403, "Видеотест доступен учащимся и преподавателям")
    return user


def _own_run(db: Session, run_id: int, user: User) -> VideoQuizRun:
    run = db.get(VideoQuizRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(404, "Попытка не найдена")
    return run


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


def _public_question(question, lang: str, test_title: str = "") -> dict:
    data = question.public(lang)
    data["test_title"] = test_title
    return data


@router.get("/sections")
def sections(lang: Lang = "ru", user: User = Depends(_student)) -> dict:
    """Разделы и тесты: два раздела, в каждом девять тестов по сценариям и общий."""
    return {
        "total": TOTAL,
        "sections": [
            {
                **section.public(lang),
                "tests": [test.public(lang) for test in section_tests(section.key)],
            }
            for section in SECTIONS
        ],
    }


@router.post("/start")
def start(payload: StartIn, db: Session = Depends(get_db),
          user: User = Depends(_student)) -> dict:
    """Новый заход: вопросы выбранного теста в случайном порядке."""
    test = by_test(payload.test)
    if test is None:
        raise HTTPException(422, "Нет такого теста")
    # вопросы теста с учётом правок преподавателя (скрытые не берём)
    edited = {q.id: q for q in quizedit.apply_all(db)}
    picked = [edited[qid] for qid in test.question_ids if qid in edited]
    import random as _random
    _random.shuffle(picked)
    if not picked:
        raise HTTPException(422, "В этом тесте нет доступных вопросов")
    run = VideoQuizRun(
        user_id=user.id,
        section=test.key,          # в этом поле теперь ключ теста
        mode=payload.mode,
        lang=payload.lang,
        question_ids=dumps([q.id for q in picked]),
        option_orders=dumps({}),   # вариантов больше нет
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
        "test": test.key,
        "test_title": test.title[run.lang],
        "section": test.section,
        "total": len(picked),
        "items": [_public_question(q, run.lang, test.title[run.lang]) for q in picked],
    }


@router.post("/answer")
def answer(payload: AnswerIn, db: Session = Depends(get_db),
           user: User = Depends(_student)) -> dict:
    """Ответ словами. В обучении сразу вердикт и эталон, в зачёте — только приём ответа."""
    run = _own_run(db, payload.run_id, user)
    if run.finished_at is not None:
        raise HTTPException(409, "Попытка уже завершена")
    question = quizedit.get_question(db, payload.question_id) or by_id(payload.question_id)
    run_question_ids = [int(qid) for qid in (loads(run.question_ids, []) or [])]
    if question is None or question.id not in run_question_ids:
        raise HTTPException(404, "Такого вопроса нет в этой попытке")
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(422, "Пустой ответ")
    answers = _answers(run)
    if str(question.id) in answers:
        raise HTTPException(409, "На этот вопрос уже есть ответ")

    result = match(question, text)
    if result["verdict"] == "retry":
        # «не расслышал»: не считаем ошибкой, просим сказать иначе
        return {"question_id": question.id, "accepted": False, "retry": True,
                "text": text, "hint": "Не разобрал ответ — сформулируйте иначе."}

    answers[str(question.id)] = {
        "text": text,
        "verdict": result["verdict"],
        "coverage": result["coverage"],
        "correct": result["verdict"] in ("correct", "partial"),
        # по критериям чек-листа: что закрыто, что нет (для разбора после ответа)
        "criteria": result.get("criteria", []),
        "score": result.get("score"),
        "doses": result.get("doses", []),
    }
    run.answers = dumps(answers)
    db.commit()

    if run.mode == "testing":
        return {"question_id": question.id, "accepted": True}

    return {
        "question_id": question.id,
        "accepted": True,
        "correct": result["verdict"] in ("correct", "partial"),
        "verdict": result["verdict"],
        "coverage": result["coverage"],
        "matched": result["matched"],
        "missed": result["missed"],
        "reference": question.reference[run.lang],
        "explain": question.explain[run.lang],
        "checklist": question.checklist,
        "criteria": result.get("criteria", []),
        "score": result.get("score"),
        "doses": result.get("doses", []),
    }


@router.get("/voice/status")
def voice_status(user: User = Depends(_student)) -> dict:
    """Что доступно для ответа: распознавание речи и проверка смысла на сервере."""
    from .. import semantic_onnx

    return {
        "server": speech.status(),
        "hint": "server" if speech.status()["available"] else "browser",
        "semantic": semantic_onnx.status(),
    }


@router.post("/transcribe")
def transcribe(payload: TranscribeIn, user: User = Depends(_student)) -> dict:
    """Распознать короткую запись на сервере (если включён VOICE_ENABLED=1).

    Аудио живёт только в памяти запроса: не сохраняем на диск и не пишем в БД.
    """
    state = speech.status()
    if not state["available"]:
        raise HTTPException(503, "Серверное распознавание выключено (нет модели или VOICE_ENABLED=0)")
    if speech.encoded_size(payload.audio) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(413, "Слишком длинная запись — говорите короче (до 30 секунд)")
    audio = speech.decode_base64(payload.audio)
    if not audio or len(audio) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(422 if not audio else 413,
                            "Пустая или битая запись" if not audio
                            else "Слишком длинная запись — говорите короче (до 30 секунд)")
    try:
        result = speech.get_service().transcribe(audio, payload.lang)
    except ValueError as error:  # не аудио или битый контейнер — виноват не сервер
        raise HTTPException(422, f"Не удалось прочитать запись: {error}") from error
    except Exception as error:  # модель не загрузилась и т.п.
        raise HTTPException(500, f"Не удалось распознать запись: {error}") from error
    return {"text": result["text"], "language": result["language"], "provider": "whisper"}


@router.post("/voice")
def voice(payload: VoiceIn, db: Session = Depends(get_db),
          user: User = Depends(_student)) -> dict:
    """Голосовой ответ: браузер распознал речь, сервер показывает, что услышал."""
    run = _own_run(db, payload.run_id, user)
    question = by_id(payload.question_id)
    run_question_ids = [int(qid) for qid in (loads(run.question_ids, []) or [])]
    if question is None or question.id not in run_question_ids:
        raise HTTPException(404, "Такого вопроса нет в этой попытке")
    if not (payload.transcript or "").strip():
        raise HTTPException(422, "Пустая фраза")
    preview = match(question, payload.transcript)
    return {
        "question_id": question.id,
        "transcript": payload.transcript,
        "recognised": preview["verdict"] != "retry",
        "matched": preview["matched"][:5],
        "doses": preview.get("doses", []),
        "mode": run.mode,
    }


def _summary(run: VideoQuizRun) -> dict:
    """Итог попытки: считается из сохранённых ответов (одинаково при повторном запросе)."""
    lang = run.lang
    answers = _answers(run)
    questions = _run_questions(run)
    details = []
    score = 0
    for question in questions:
        stored = answers.get(str(question.id)) or {}
        good = bool(stored.get("correct"))
        # полный ответ — 1 балл, «сказано не всё» — 0,5
        credit = 1.0 if stored.get("verdict") == "correct" else (0.5 if good else 0.0)
        score += credit
        details.append({
            "id": question.id,
            "text": question.text[lang],
            "answer": stored.get("text"),
            "verdict": stored.get("verdict"),
            "coverage": stored.get("coverage"),
            "correct": good,
            "credit": credit,
            "reference": question.reference[lang],
            "explain": question.explain[lang],
            "checklist": question.checklist,
        })

    total = len(questions) or run.total or 1
    score = round(score, 2)
    percent = round(score * 100 / total, 1)
    code, text = verdict(percent, lang)
    test = by_test(run.section)
    return {
        "id": run.id,
        "score": score,
        "total": total,
        "percent": percent,
        "verdict": code,
        "verdict_text": text,
        "mode": run.mode,
        "section": test.section if test else run.section,
        "test": run.section,
        "test_title": test.title[lang] if test else run.section,
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
                           "test": run.section})
    summary["already_finished"] = already
    return summary


@router.get("/results")
def results(db: Session = Depends(get_db), user: User = Depends(_student)) -> dict:
    """История: только завершённые попытки, по одной строке на заход."""
    rows = db.scalars(
        select(VideoQuizRun)
        .where(VideoQuizRun.user_id == user.id, VideoQuizRun.finished_at.is_not(None))
        .order_by(VideoQuizRun.finished_at.desc())
        .limit(50)
    ).all()
    items = []
    for row in rows:
        test = by_test(row.section)
        items.append({
            "id": row.id,
            "score": row.score,
            "total": row.total,
            "percent": row.percent,
            "mode": row.mode,
            "section": test.section if test else row.section,
            "test": row.section,
            "test_title": test.title["ru"] if test else row.section,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        })
    return {"items": items}


@router.get("/results/{run_id}")
def result_detail(run_id: int, db: Session = Depends(get_db),
                  user: User = Depends(_student)) -> dict:
    """Разбор завершённой попытки: ответ учащегося и эталон."""
    run = _own_run(db, run_id, user)
    if run.finished_at is None:
        raise HTTPException(404, "Попытка не завершена")
    return _summary(run)
