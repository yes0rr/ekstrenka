"""Правки вопросов преподавателем (поверх банка quizbank.py).

Зачем отдельный слой:
    банк вопросов — это код (quizbank.py), его нельзя менять из браузера;
    а преподавателю нужно поправить формулировку, эталон или ключевые слова,
    не трогая программу. Поэтому правки лежат в таблице quiz_overrides:
    если для вопроса есть строка — берём её, если нет — берём вопрос из банка.

Ключевые слова хранятся строкой: группы разделяются «|», синонимы внутри
группы — запятой. Пример: «эпинефрин, адреналин | в/м, внутримышечно | бедро».

Любую правку можно отменить (DELETE) — вопрос вернётся к исходному виду.
"""
from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import QuizOverride, utcnow
from .quizbank import QUESTIONS, QUESTION_BY_ID, Question
from .services import dumps, loads


def keys_to_text(groups) -> str:
    """Группы ключей → строка для формы: «а, б | в, г»."""
    return " | ".join(", ".join(group) for group in groups or ())


def text_to_keys(text: str) -> tuple[tuple[str, ...], ...]:
    """Строка из формы → группы ключей. Пустые куски выбрасываются."""
    groups: list[tuple[str, ...]] = []
    for chunk in (text or "").replace(";", "|").split("|"):
        words = tuple(w.strip().lower() for w in chunk.split(",") if w.strip())
        if words:
            groups.append(words)
    return tuple(groups)


def _all(db: Session) -> dict[int, QuizOverride]:
    return {row.question_id: row for row in db.scalars(select(QuizOverride)).all()}


def apply_all(db: Session) -> list[Question]:
    """Все вопросы банка с учётом правок (скрытые не попадают)."""
    overrides = _all(db)
    result: list[Question] = []
    for question in QUESTIONS:
        row = overrides.get(question.id)
        if row is None:
            result.append(question)
            continue
        if row.hidden:
            continue
        result.append(apply_one(question, row))
    return result


def apply_one(question: Question, row: QuizOverride) -> Question:
    """Один вопрос с подставленными правками."""
    return replace(
        question,
        text={"ru": row.text or question.text["ru"], "en": question.text["en"]},
        reference={"ru": row.reference or question.reference["ru"], "en": question.reference["en"]},
        explain={"ru": row.explain or question.explain["ru"], "en": question.explain["en"]},
        keys=text_to_keys(row.keys) if row.keys else question.keys,
    )


def get_question(db: Session, question_id: int) -> Question | None:
    """Вопрос с правками — им пользуется проверка ответа."""
    base = QUESTION_BY_ID.get(int(question_id))
    if base is None:
        return None
    row = db.scalar(select(QuizOverride).where(QuizOverride.question_id == int(question_id)))
    return apply_one(base, row) if row is not None else base


def edited_ids(db: Session) -> set[int]:
    return set(_all(db))


def hidden_ids(db: Session) -> set[int]:
    return {qid for qid, row in _all(db).items() if row.hidden}


def save(db: Session, question_id: int, *, text: str, reference: str, explain: str,
         keys: str, hidden: bool, author_id: int | None) -> QuizOverride:
    """Сохранить правку. Пустые поля = «как в банке»."""
    base = QUESTION_BY_ID.get(int(question_id))
    if base is None:
        raise KeyError(question_id)
    row = db.scalar(select(QuizOverride).where(QuizOverride.question_id == int(question_id)))
    if row is None:
        row = QuizOverride(question_id=int(question_id))
        db.add(row)
    # если преподаватель вернул исходный текст — не храним копию
    row.text = None if (text or "").strip() == base.text["ru"] else (text or "").strip() or None
    row.reference = (None if (reference or "").strip() == base.reference["ru"]
                     else (reference or "").strip() or None)
    row.explain = (None if (explain or "").strip() == base.explain["ru"]
                   else (explain or "").strip() or None)
    row.keys = (None if text_to_keys(keys) == base.keys else (keys or "").strip() or None)
    row.hidden = bool(hidden)
    row.author_id = author_id
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


def reset(db: Session, question_id: int) -> bool:
    """Отменить правку: вопрос возвращается к варианту из банка."""
    row = db.scalar(select(QuizOverride).where(QuizOverride.question_id == int(question_id)))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def public_row(db: Session, question: Question) -> dict:
    """Вопрос для страницы проверки: исходник + текущее состояние."""
    row = db.scalar(select(QuizOverride).where(QuizOverride.question_id == question.id))
    return {
        "id": question.id,
        "test": question.test,
        "section": question.section,
        "scenario": question.scenario,
        "text": question.text["ru"],
        "reference": question.reference["ru"],
        "explain": question.explain["ru"],
        "keys": keys_to_text(question.keys),
        "hidden": bool(row.hidden) if row else False,
        "edited": row is not None,
        "base_text": question.text["ru"],
        "base_reference": question.reference["ru"],
        "base_keys": keys_to_text(question.keys),
    }
