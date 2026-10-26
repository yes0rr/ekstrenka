"""Логика проверки ответов (алгоритм — без нейросети)."""
from __future__ import annotations

import json
from typing import Any

from .models import Answer, Question


def loads(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def check_answer(question: Question, value: Any) -> tuple[bool | None, float]:
    """Возвращает (верно/неверно/None если проверить нельзя, начисленные баллы)."""
    correct = loads(question.correct, None)

    if question.kind == "single":
        if correct is None:
            return None, 0.0
        ok = normalize(value) == normalize(correct)
        return ok, float(question.points) if ok else 0.0

    if question.kind == "multiple":
        if correct is None:
            return None, 0.0
        given = {normalize(v) for v in (value or [])}
        expect = {normalize(v) for v in correct}
        if not expect:
            return None, 0.0
        ok = given == expect
        if ok:
            return True, float(question.points)
        # частичный балл за неполный, но корректный набор
        partial = len(given & expect) / len(expect) * float(question.points)
        return False, round(partial * 0.5, 2)

    # свободный текстовый ответ: сравнение с эталоном (нормализация + допустимые варианты)
    if not correct or question.kind == "text_manual":
        return None, 0.0
    if isinstance(correct, str):
        variants = [correct]
    else:
        variants = list(correct)
    ok = normalize(value) in {normalize(v) for v in variants}
    return ok, float(question.points) if ok else 0.0


def recompute_score(attempt) -> None:
    """Пересчитать суммарный балл попытки по сохранённым ответам."""
    attempt.score = round(sum(a.awarded_points for a in attempt.answers), 2)
    attempt.max_score = float(sum(q.points for q in attempt.test.questions))


def question_payload(question: Question, *, for_student: bool) -> dict[str, Any]:
    """Опции и правильные ответы не отдаём учащемуся в режиме тестирования."""
    data = {
        "id": question.id,
        "order_index": question.order_index,
        "text": question.text,
        "kind": question.kind,
        "options": loads(question.options, []),
        "points": question.points,
    }
    if for_student:
        return data
    data["correct"] = loads(question.correct, None)
    data["hint"] = question.hint
    return data


def answer_summary(answer: Answer) -> dict[str, Any]:
    return {
        "question_id": answer.question_id,
        "question": answer.question.text if answer.question else None,
        "value": loads(answer.value, None),
        "is_correct": answer.is_correct,
        "awarded_points": answer.awarded_points,
        "is_manual": answer.is_manual,
    }
