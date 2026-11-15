"""Видеотест «Экстренка»: разделы «Диагностика» и «Лечение», ответы словами.

Модуль-обёртка: сами вопросы лежат в quizbank.py, проверка ответа по смыслу —
в answermatch.py. Здесь только то, чем пользуются роутеры и тесты:
разделы, тесты, вердикты.
"""
from __future__ import annotations

from .answermatch import match
from .quizbank import (  # noqa: F401  (реэкспорт для роутеров и тестов)
    LANGS,
    QUESTIONS,
    QUESTION_BY_ID,
    RUN_SIZE,
    SCENARIOS,
    SECTION_BY_KEY,
    SECTIONS,
    TEST_BY_KEY,
    TESTS,
    TOTAL,
    Question,
    Section,
    Test,
    by_id,
    by_test,
    pick_questions,
    section_tests,
)

# Критерии оценки эксперта из CSV: 90–100 отлично, 80–89 хорошо,
# 70–79 удовлетворительно, меньше 70 — неудовлетворительно.
VERDICTS: tuple[tuple[float, str, str], ...] = (
    (90, "excellent", "Отлично — алгоритм знаете уверенно"),
    (80, "good", "Хорошо — есть единичные пробелы"),
    (70, "fair", "Удовлетворительно — стоит повторить слабые темы"),
    (0, "bad", "Неудовлетворительно — начните с «{guide}»"),
)

VERDICTS_EN: tuple[tuple[float, str, str], ...] = (
    (90, "excellent", "Excellent — you know the algorithm confidently"),
    (80, "good", "Good — a few gaps remain"),
    (70, "fair", "Satisfactory — review the weak topics"),
    (0, "bad", "Unsatisfactory — start with {guide}"),
)

GUIDE_URL = "/instruction/emergency-help"
GUIDE_LABEL = {"ru": "инструкции по ЭМП", "en": "the emergency care guide"}


def verdict(percent: float, lang: str = "ru") -> tuple[str, str]:
    """Процент → (код вердикта, текст) по шкале эксперта."""
    table = VERDICTS_EN if lang == "en" else VERDICTS
    for threshold, code, text in table:
        if percent >= threshold:
            return code, text.format(guide=GUIDE_LABEL.get(lang, GUIDE_LABEL["ru"]))
    code, text = table[-1][1], table[-1][2]
    return code, text.format(guide=GUIDE_LABEL.get(lang, GUIDE_LABEL["ru"]))


def check(question: Question, answer: str) -> dict:
    """Проверка свободного ответа: вердикт, покрытие, эталон, пояснение."""
    result = match(question, answer)
    result.update({
        "question_id": question.id,
        "explain": question.explain["ru"],
        "checklist": question.checklist,
    })
    return result
