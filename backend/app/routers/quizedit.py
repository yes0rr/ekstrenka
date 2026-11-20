"""Правка вопросов видеотеста преподавателем.

API:
    GET    /api/quiz-edit/questions      — все вопросы с текущими правками
    POST   /api/quiz-edit/{question_id}  — сохранить правку
    DELETE /api/quiz-edit/{question_id}  — вернуть исходный вариант из банка
    GET    /api/quiz-edit/check/{qid}    — «как проверится ответ» (песочница)

Доступно только преподавателю.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import quizedit
from ..answermatch import match
from ..db import get_db
from ..deps import require_teacher
from ..models import User
from ..quizbank import QUESTIONS, SCENARIO_BY_NUM, SECTION_BY_KEY
from ..security import write_log

router = APIRouter(prefix="/api/quiz-edit", tags=["quiz-edit"])


class EditIn(BaseModel):
    text: str = Field(default="", max_length=1000)
    reference: str = Field(default="", max_length=2000)
    explain: str = Field(default="", max_length=2000)
    keys: str = Field(default="", max_length=2000)
    hidden: bool = False


@router.get("/questions")
def list_questions(db: Session = Depends(get_db), user: User = Depends(require_teacher)) -> dict:
    """Все вопросы: исходник, текущий текст, признак правки."""
    items = []
    for base in QUESTIONS:
        question = quizedit.get_question(db, base.id) or base   # с учётом правок
        row = quizedit.public_row(db, question)
        row["base_text"] = base.text["ru"]
        row["base_reference"] = base.reference["ru"]
        row["base_keys"] = quizedit.keys_to_text(base.keys)
        row["scenario_title"] = SCENARIO_BY_NUM[question.scenario]["ru"]
        row["section_title"] = SECTION_BY_KEY[question.section].title["ru"]
        row["test_title"] = next(
            (t.title["ru"] for t in __import__("backend.app.quizbank", fromlist=["TESTS"]).TESTS
             if t.key == question.test), question.test)
        items.append(row)
    return {"total": len(items), "items": items}


@router.post("/{question_id}")
def save_edit(question_id: int, payload: EditIn, db: Session = Depends(get_db),
              user: User = Depends(require_teacher)) -> dict:
    try:
        quizedit.save(db, question_id, text=payload.text, reference=payload.reference,
                      explain=payload.explain, keys=payload.keys, hidden=payload.hidden,
                      author_id=user.id)
    except KeyError:
        raise HTTPException(404, "Нет такого вопроса")
    write_log(db, "quiz_question_edited", user_id=user.id, entity="quiz_question",
              entity_id=question_id, payload={"hidden": payload.hidden})
    question = quizedit.get_question(db, question_id)
    return {"ok": True, "question": quizedit.public_row(db, question)}


@router.delete("/{question_id}")
def reset_edit(question_id: int, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)) -> dict:
    removed = quizedit.reset(db, question_id)
    write_log(db, "quiz_question_reset", user_id=user.id, entity="quiz_question",
              entity_id=question_id, payload={})
    return {"ok": True, "reset": removed}


@router.get("/check/{question_id}")
def check_answer(question_id: int, answer: str = "", db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)) -> dict:
    """Песочница: преподаватель пишет ответ и видит вердикт по текущим правкам."""
    question = quizedit.get_question(db, question_id)
    if question is None:
        raise HTTPException(404, "Нет такого вопроса")
    result = match(question, answer)
    return {"verdict": result["verdict"], "coverage": result["coverage"],
            "matched": result["matched"], "missed": result["missed"],
            "blocked": result.get("blocked", [])}
