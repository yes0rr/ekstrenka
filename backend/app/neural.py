"""Заглушка нейропроверки.

Точка подключения будущей модели: сюда придёт текст ответа / расшифровка аудио /
видеоряд, а вернётся вердикт по критериям испытания.

Пока NEURAL_ENABLED=0 — функция возвращает статус "pending" ("ожидает проверки"),
и попытка оценивается только алгоритмом (services.check_answer).

Когда появится модель — достаточно реализовать evaluate_attempt() и включить
NEURAL_ENABLED=1. Сигнатура и формат ответа менять не нужно.
"""
from __future__ import annotations

from typing import Any

from .config import settings


async def evaluate_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    """
    payload = {
        "attempt_id": int,
        "test_title": str,
        "criteria": str | None,
        "mode": "training" | "testing",
        "subject_type": "human" | "imitation",
        "answers": [{"question": str, "answer": str, "is_correct": bool | None}],
        "media": {"camera": bool, "mic": bool, "seconds": int},
    }
    return {"status": "pending" | "done" | "failed",
            "score": float | None,
            "comment": str | None,
            "verdict": "pass" | "fail" | None}
    """
    if not settings.neural_enabled:
        return {
            "status": "pending",
            "score": None,
            "comment": "Нейропроверка не подключена — оценка выставлена по алгоритму.",
            "verdict": None,
        }

    # TODO: здесь будет вызов модели. Пока та же заглушка.
    return {"status": "pending", "score": None, "comment": None, "verdict": None}
