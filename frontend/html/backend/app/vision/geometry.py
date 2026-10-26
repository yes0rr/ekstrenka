"""Геометрия по точкам скелета: из 33 точек MediaPipe — в понятные метрики СЛР.

Здесь нет ни MediaPipe, ни numpy, ни БД — только математика над координатами.
Поэтому файл тестируется без установленной модели (см. tests/test_vision.py)
и переносится куда угодно.

Точки MediaPipe Pose (индексы стандартные):
    11, 12 — плечи (левое, правое)
    13, 14 — локти
    15, 16 — запястья
    23, 24 — тазобедренные суставы

Две системы координат:
    landmarks        — нормализованные (0..1) координаты кадра, y растёт ВНИЗ;
                       по ним считаем углы и «стоит ли человек боком»;
    world_landmarks  — метры относительно центра таза, по ним считаем САНТИМЕТРЫ.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

# индексы точек
L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HP, R_HP = 23, 24

# пороги (совпадают с frontend-логикой и паспортом станции)
ARM_STRAIGHT_DEG = 160.0   # локоть не согнут, если угол ≥ 160°
ARM_VERTICAL_DEG = 28.0    # отклонение плечи→кисти от вертикали
HANDS_TOGETHER_CM = 12.0   # расстояние между запястьями
HANDS_MIDLINE_CM = 16.0    # боковое смещение кистей от линии плеч
SIDE_VIEW_RATIO = 0.45     # разнос плеч / длина корпуса — «камера стоит сбоку»

Vec = tuple[float, float, float]


# --------------------------------------------------------------- базовая математика
def _p(points: Sequence[Any], index: int) -> Vec:
    """Точка может быть объектом MediaPipe (.x/.y/.z) или обычным кортежем."""
    pt = points[index]
    if hasattr(pt, "x"):
        return (float(pt.x), float(pt.y), float(pt.z))
    return (float(pt[0]), float(pt[1]), float(pt[2]))


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def norm(v: Vec) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def mid(a: Vec, b: Vec) -> Vec:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def angle_deg(a: Vec, b: Vec, c: Vec) -> float:
    """Угол ABC в градусах (в вершине b). 180° — полностью прямая линия."""
    ba, bc = sub(a, b), sub(c, b)
    nb, nc = norm(ba), norm(bc)
    if nb < 1e-9 or nc < 1e-9:
        return 0.0
    cos = (ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2]) / (nb * nc)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def deviation_from_vertical_deg(shoulders_mid: Vec, wrists_mid: Vec) -> float:
    """Насколько линия «плечи → кисти» отклонена от вертикали (в нормализованных
    координатах кадра вертикаль = ось Y). 0° — строго вертикально."""
    dx = wrists_mid[0] - shoulders_mid[0]
    dy = wrists_mid[1] - shoulders_mid[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 0.0
    return abs(math.degrees(math.atan2(dx, abs(dy) if abs(dy) > 1e-9 else 1e-9)))


# --------------------------------------------------------------- метрики одного кадра
def frame_metrics(landmarks: Sequence[Any], world_landmarks: Sequence[Any] | None = None) -> dict[str, Any]:
    """Посчитать всё, что можно понять по одному кадру.

    Возвращает словарь с сырыми числами; решение «хорошо/плохо» принимает агрегатор,
    чтобы пороги можно было менять в одном месте.
    """
    l_sh, r_sh = _p(landmarks, L_SH), _p(landmarks, R_SH)
    l_el, r_el = _p(landmarks, L_EL), _p(landmarks, R_EL)
    l_wr, r_wr = _p(landmarks, L_WR), _p(landmarks, R_WR)

    sh_mid = mid(l_sh, r_sh)
    wr_mid = mid(l_wr, r_wr)

    out: dict[str, Any] = {
        "arm_left_deg": round(angle_deg(l_sh, l_el, l_wr), 1),
        "arm_right_deg": round(angle_deg(r_sh, r_el, r_wr), 1),
        "vertical_deg": round(deviation_from_vertical_deg(sh_mid, wr_mid), 1),
    }
    out["arm_left_straight"] = out["arm_left_deg"] >= ARM_STRAIGHT_DEG
    out["arm_right_straight"] = out["arm_right_deg"] >= ARM_STRAIGHT_DEG
    out["arms_straight"] = out["arm_left_straight"] and out["arm_right_straight"]
    out["arms_vertical"] = out["vertical_deg"] <= ARM_VERTICAL_DEG

    # длина корпуса и разнос плеч в кадре — проверка, что камера стоит сбоку
    l_hp, r_hp = _p(landmarks, L_HP), _p(landmarks, R_HP)
    torso = norm(sub(sh_mid, mid(l_hp, r_hp)))
    spread = norm(sub(l_sh, r_sh))
    ratio = (spread / torso) if torso > 1e-6 else 1.0
    out["side_ratio"] = round(ratio, 3)
    out["side_view"] = ratio < SIDE_VIEW_RATIO

    # сантиметры — только из world-координат (метры)
    if world_landmarks is not None:
        w_l_wr, w_r_wr = _p(world_landmarks, L_WR), _p(world_landmarks, R_WR)
        w_l_sh, w_r_sh = _p(world_landmarks, L_SH), _p(world_landmarks, R_SH)
        w_sh_mid = mid(w_l_sh, w_r_sh)
        w_wr_mid = mid(w_l_wr, w_r_wr)

        out["hands_together_cm"] = round(norm(sub(w_l_wr, w_r_wr)) * 100, 1)
        out["hands_together"] = out["hands_together_cm"] <= HANDS_TOGETHER_CM

        # боковое смещение кистей: раскладываем вектор «плечи→кисти» вдоль линии плеч
        axis = sub(w_r_sh, w_l_sh)
        axis_len = norm(axis)
        if axis_len > 1e-6:
            unit = (axis[0] / axis_len, axis[1] / axis_len, axis[2] / axis_len)
            d = sub(w_wr_mid, w_sh_mid)
            lateral = abs(d[0] * unit[0] + d[1] * unit[1] + d[2] * unit[2])
        else:
            lateral = 0.0
        out["hands_midline_cm"] = round(lateral * 100, 1)
        out["hands_on_midline"] = out["hands_midline_cm"] <= HANDS_MIDLINE_CM

        # сигнал для темпа и глубины: вертикальное положение кистей в метрах
        out["wrists_y"] = round(w_wr_mid[1], 5)
    else:
        out["hands_together_cm"] = None
        out["hands_together"] = None
        out["hands_midline_cm"] = None
        out["hands_on_midline"] = None
        out["wrists_y"] = None

    return out


# --------------------------------------------------------------- темп и глубина
class CompressionTracker:
    """Считает темп, глубину и ритмичность по вертикальному сигналу кистей.

    Логика (та же, что в браузерной версии):
      1) убираем «дрейф» тела — вычитаем медленную EMA (τ ≈ 2.2 с);
      2) по сглаженному сигналу ищем пики (верхняя точка каждой компрессии);
      3) темп = медиана интервалов между пиками;
      4) глубина = размах «пик → впадина» в сантиметрах;
      5) ритмичность = коэффициент вариации интервалов (0 — идеально ровно).
    """

    def __init__(self, tau_slow: float = 2.2, tau_fast: float = 0.06,
                 min_gap_s: float = 0.2, history_s: float = 12.0) -> None:
        self.tau_slow = tau_slow
        self.tau_fast = tau_fast
        self.min_gap_s = min_gap_s
        self.history_s = history_s
        self._t: list[float] = []
        self._signal: list[float] = []      # detrended, почти сырой (амплитуда)
        self._smooth: list[float] = []      # сглаженный (поиск пиков)
        self._slow: float | None = None
        self._fast: float | None = None

    def reset(self) -> None:
        self._t.clear()
        self._signal.clear()
        self._smooth.clear()
        self._slow = self._fast = None

    def add(self, t: float, y: float) -> None:
        """t — секунды, y — вертикальное положение кистей в метрах."""
        if self._slow is None:
            self._slow = y
            self._fast = 0.0
        # dt для EMA берём по фактическому шагу (кадры приходят неравномерно)
        dt = (t - self._t[-1]) if self._t else 1 / 15
        dt = max(1e-3, min(dt, 1.0))
        a_slow = 1 - math.exp(-dt / self.tau_slow)
        self._slow += (y - self._slow) * a_slow
        sig = y - self._slow
        a_fast = 1 - math.exp(-dt / self.tau_fast)
        self._fast = sig if self._fast is None else self._fast + (sig - self._fast) * a_fast
        self._t.append(t)
        self._signal.append(sig)
        self._smooth.append(self._fast)
        # обрезаем историю
        while self._t and t - self._t[0] > self.history_s:
            self._t.pop(0)
            self._signal.pop(0)
            self._smooth.pop(0)

    def peaks(self) -> list[int]:
        """Индексы локальных максимумов сглаженного сигнала."""
        s = self._smooth
        if len(s) < 5:
            return []
        amp = max(abs(v) for v in s)
        if amp < 1e-6:
            return []
        threshold = 0.35 * amp
        found: list[int] = []
        for i in range(1, len(s) - 1):
            if s[i] > threshold and s[i] >= s[i - 1] and s[i] > s[i + 1]:
                if found and self._t[i] - self._t[found[-1]] < self.min_gap_s:
                    # слишком близко — оставляем более высокий пик
                    if s[i] > s[found[-1]]:
                        found[-1] = i
                    continue
                found.append(i)
        return found

    def result(self) -> dict[str, Any]:
        idx = self.peaks()
        if len(idx) < 3:
            return {"tempo_bpm": None, "depth_cm": None, "rhythm_cv": None,
                    "compressions": max(0, len(idx)), "ready": False}

        intervals = [self._t[idx[i + 1]] - self._t[idx[i]] for i in range(len(idx) - 1)]
        intervals = [v for v in intervals if v > 0]
        if not intervals:
            return {"tempo_bpm": None, "depth_cm": None, "rhythm_cv": None,
                    "compressions": len(idx), "ready": False}

        intervals.sort()
        median_dt = intervals[len(intervals) // 2]
        mean_dt = sum(intervals) / len(intervals)
        var = sum((v - mean_dt) ** 2 for v in intervals) / len(intervals)
        cv = math.sqrt(var) / mean_dt if mean_dt > 0 else None

        # глубина: среднее «пик» минус среднее «впадина» между соседними пиками
        peaks_val = [self._signal[i] for i in idx]
        troughs = []
        for i in range(len(idx) - 1):
            chunk = self._signal[idx[i]:idx[i + 1] + 1]
            if chunk:
                troughs.append(min(chunk))
        depth_cm = None
        if peaks_val and troughs:
            depth_cm = round((sum(peaks_val) / len(peaks_val) -
                              sum(troughs) / len(troughs)) * 100, 1)

        return {
            "tempo_bpm": round(60.0 / median_dt, 1) if median_dt > 0 else None,
            "depth_cm": depth_cm,
            "rhythm_cv": round(cv, 3) if cv is not None else None,
            "compressions": len(idx),
            "ready": True,
        }


# --------------------------------------------------------------- агрегатор сессии
@dataclass
class SessionAggregator:
    """Копит кадры одной попытки и выдаёт итоговые показатели."""

    tracker: CompressionTracker = field(default_factory=CompressionTracker)
    frames_total: int = 0
    frames_with_pose: int = 0
    _checks: dict[str, int] = field(default_factory=lambda: {
        "arms_straight": 0, "arms_vertical": 0, "hands_together": 0,
        "hands_on_midline": 0, "side_view": 0,
    })
    _last: dict[str, Any] = field(default_factory=dict)
    _t0: float | None = None
    _t_last: float | None = None

    def add_frame(self, t: float, fm: dict[str, Any]) -> None:
        self.frames_total += 1
        if self._t0 is None:
            self._t0 = t
        self._t_last = t
        if not fm.get("pose"):
            return
        self.frames_with_pose += 1
        for key in self._checks:
            if fm.get(key):
                self._checks[key] += 1
        if fm.get("wrists_y") is not None:
            self.tracker.add(t, float(fm["wrists_y"]))
        self._last = fm

    def _pct(self, key: str) -> float | None:
        if not self.frames_with_pose:
            return None
        return round(100.0 * self._checks[key] / self.frames_with_pose, 1)

    def snapshot(self) -> dict[str, Any]:
        """Живые показатели для интерфейса (обновляются по ходу станции)."""
        live = self.tracker.result()
        live.update({
            "frames_total": self.frames_total,
            "frames_with_pose": self.frames_with_pose,
            "arms_straight_pct": self._pct("arms_straight"),
            "arms_vertical_pct": self._pct("arms_vertical"),
            "hands_together_pct": self._pct("hands_together"),
            "hands_on_midline_pct": self._pct("hands_on_midline"),
            "side_view_pct": self._pct("side_view"),
            "last_frame": self._last or None,
            "duration_s": round((self._t_last - self._t0), 1) if self._t0 is not None else 0,
        })
        return live

    def summary(self) -> dict[str, Any]:
        data = self.snapshot()
        data["checks"] = dict(self._checks)
        return data
