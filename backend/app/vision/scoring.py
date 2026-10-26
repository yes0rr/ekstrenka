"""Оценка техники по агрегатам видеоанализа.

Чистый Python, без зависимостей: на вход приходят числа из SessionAggregator,
на выход — балл 0–100, комментарий и вердикт. Пороги взяты из паспорта станции
ЭМП и совпадают с рекомендациями по СЛР (100–120 компрессий/мин, 5–6 см).

Функция используется в двух местах:
  1) neural.evaluate_attempt() — когда попытка завершена;
  2) тесты — можно проверить, что пороги дают ожидаемый балл.
"""
from __future__ import annotations

from typing import Any

# веса критериев (сумма = 100)
W_TEMPO = 25
W_DEPTH = 25
W_ARMS = 20
W_VERTICAL = 15
W_HANDS = 15

TEMPO_IDEAL = (100.0, 120.0)
TEMPO_OK = (80.0, 140.0)
DEPTH_IDEAL = (5.0, 6.0)
DEPTH_OK = (4.0, 7.0)
PCT_GOOD = 85.0     # доля кадров, при которой критерий считаем выполненным


def _tempo_points(bpm: float | None) -> tuple[float, str | None]:
    if bpm is None:
        return 0.0, "темп не определён"
    lo, hi = TEMPO_IDEAL
    if lo <= bpm <= hi:
        return float(W_TEMPO), None
    olo, ohi = TEMPO_OK
    if olo <= bpm <= ohi:
        return W_TEMPO * 0.6, f"темп {bpm:.0f}/мин вне коридора 100–120"
    return 0.0, f"темп {bpm:.0f}/мин"


def _depth_points(cm: float | None) -> tuple[float, str | None]:
    if cm is None:
        return 0.0, "глубина не определена"
    lo, hi = DEPTH_IDEAL
    if lo <= cm <= hi:
        return float(W_DEPTH), None
    olo, ohi = DEPTH_OK
    if olo <= cm <= ohi:
        return W_DEPTH * 0.6, f"глубина {cm:.1f} см (норма 5–6)"
    return 0.0, f"глубина {cm:.1f} см"


def _pct_points(value: float | None, weight: int, label: str) -> tuple[float, str | None]:
    if value is None:
        return 0.0, f"{label}: нет данных"
    if value >= PCT_GOOD:
        return float(weight), None
    if value >= 50:
        return weight * (value / 100.0), f"{label}: {value:.0f}% кадров"
    return 0.0, f"{label}: {value:.0f}% кадров"


def score_from_aggregates(agg: dict[str, Any] | None) -> dict[str, Any]:
    """agg — то, что вернул SessionAggregator.summary()."""
    if not agg or not agg.get("frames_with_pose"):
        return {
            "status": "failed",
            "score": None,
            "comment": "В кадре не распознан человек — техника не оценена.",
            "verdict": None,
        }

    score = 0.0
    notes: list[str] = []

    for points, note in (
        _tempo_points(agg.get("tempo_bpm")),
        _depth_points(agg.get("depth_cm")),
        _pct_points(agg.get("arms_straight_pct"), W_ARMS, "руки прямые"),
        _pct_points(agg.get("arms_vertical_pct"), W_VERTICAL, "руки вертикальны"),
        _pct_points(agg.get("hands_together_pct"), W_HANDS, "кисти соединены"),
    ):
        score += points
        if note:
            notes.append(note)

    score = round(score, 1)
    verdict = "pass" if score >= 70 else "fail"

    head = (
        f"Темп {agg.get('tempo_bpm') or '—'}/мин, "
        f"глубина {agg.get('depth_cm') or '—'} см, "
        f"прямые руки {agg.get('arms_straight_pct') or 0:.0f}% кадров. "
    )
    tail = ("Замечания: " + "; ".join(notes)) if notes else "Замечаний по технике нет."
    return {
        "status": "done",
        "score": score,
        "comment": (head + tail).strip(),
        "verdict": verdict,
    }
