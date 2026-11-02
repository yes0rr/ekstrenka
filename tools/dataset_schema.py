"""Схема датасета для обучения: имена признаков, метки, русские подписи.

Один файл на всю цепочку, чтобы export_dataset.py и train_model.py не разъехались:
если добавили признак — добавили здесь, и он появился в обоих скриптах.
"""
from __future__ import annotations

# ---------------------------------------------------------------- метки
# Пять бинарных критериев. Общий балл меткой НЕ является: в нём смешаны разные ошибки.
LABELS: list[str] = [
    "tempo_ok",
    "depth_ok",
    "arms_straight_ok",
    "arms_vertical_ok",
    "hands_together_ok",
]

LABEL_RU: dict[str, str] = {
    "tempo_ok": "Темп 100–120 в минуту",
    "depth_ok": "Глубина 5–6 см",
    "arms_straight_ok": "Руки прямые (локти не согнуты)",
    "arms_vertical_ok": "Руки вертикальны",
    "hands_together_ok": "Кисти соединены",
}

# ---------------------------------------------------------------- числовые признаки
# Считаются по видео скриптом export_dataset.py и подаются модели как есть.
FEATURES: list[str] = [
    "tempo_bpm",           # темп компрессий
    "depth_cm",            # глубина компрессий
    "rhythm_cv",           # разброс интервалов: 0 — идеально ровно
    "compressions",        # сколько компрессий насчитали
    "arms_straight_pct",   # доля кадров с прямыми руками
    "arms_vertical_pct",   # доля кадров с вертикальными руками
    "hands_together_pct",  # доля кадров с соединёнными кистями
    "hands_on_midline_pct",
    "side_view_pct",       # доля кадров, где камера стоит сбоку
    "pose_ratio",          # доля кадров, где поза вообще найдена
    "duration_s",          # сколько длилась запись
    "arm_left_mean_deg",   # средний угол в левом локте
    "arm_right_mean_deg",  # средний угол в правом локте
    "arm_min_deg",         # самый согнутый локоть за попытку
    "vertical_mean_deg",   # среднее отклонение рук от вертикали
    "hands_gap_cm",        # среднее расстояние между кистями
    "side_ratio_mean",     # разнос плеч / длина корпуса (проверка ракурса)
    "wrists_amp",          # размах вертикального сигнала кистей (сырая амплитуда)
]

# ---------------------------------------------------------------- метаданные (не признаки)
META: list[str] = ["id", "file", "student", "expert", "date", "comment"]

# ---------------------------------------------------------------- пороги (текущее правило)
# Те же числа, что в backend/app/vision/scoring.py. Нужны, чтобы сравнить
# «правило сейчас» и «модель» на одной и той же разметке.
RULE_TEMPO = (100.0, 120.0)
RULE_DEPTH = (5.0, 6.0)
RULE_PCT = 85.0


def rule_prediction(label: str, row: dict) -> int | None:
    """Что говорит текущее правило (без обучения) по признакам попытки.

    Возвращает 1/0 или None, если данных не хватает.
    """
    def num(key: str) -> float | None:
        try:
            value = row.get(key)
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    if label == "tempo_ok":
        v = num("tempo_bpm")
        return None if v is None else int(RULE_TEMPO[0] <= v <= RULE_TEMPO[1])
    if label == "depth_ok":
        v = num("depth_cm")
        return None if v is None else int(RULE_DEPTH[0] <= v <= RULE_DEPTH[1])
    if label == "arms_straight_ok":
        v = num("arms_straight_pct")
        return None if v is None else int(v >= RULE_PCT)
    if label == "arms_vertical_ok":
        v = num("arms_vertical_pct")
        return None if v is None else int(v >= RULE_PCT)
    if label == "hands_together_ok":
        v = num("hands_together_pct")
        return None if v is None else int(v >= RULE_PCT)
    return None
