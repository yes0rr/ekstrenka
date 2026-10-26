"""Тесты видеоанализа: геометрия, темп/глубина, слоты, оценка.

MediaPipe и модель здесь НЕ нужны — проверяется наша математика и очередь.
Запуск:
    python -m pytest backend/tests/test_vision.py -q
"""
from __future__ import annotations

import math
import time

import pytest

from backend.app.vision.geometry import (
    HANDS_TOGETHER_CM,
    SessionAggregator,
    angle_deg,
    frame_metrics,
)
from backend.app.vision.scoring import score_from_aggregates
from backend.app.vision.slot import ACTIVE, QueueFullError, SlotManager, WAITING
from backend.app.vision.service import _decode_image


# ------------------------------------------------------------------ помощники
def make_pose(*, arms_straight: bool = True, vertical: bool = True, side: bool = True):
    """Собрать 33 точки: «идеальная» поза СЛР сверху, с возможными дефектами."""
    pts = [(0.5, 0.5, 0.0) for _ in range(33)]
    sh_l, sh_r = (0.45, 0.35, 0.0), (0.47, 0.35, 0.0)
    hp_l, hp_r = (0.45, 0.75, 0.0), (0.47, 0.75, 0.0)
    if not side:                      # камера спереди: плечи широко
        sh_l, sh_r = (0.30, 0.35, 0.0), (0.62, 0.35, 0.0)
        hp_l, hp_r = (0.32, 0.75, 0.0), (0.60, 0.75, 0.0)
    wrist_y = 0.15
    wr_x = 0.46 if vertical else 0.60     # отклонение от вертикали
    el_x = 0.46 if arms_straight else 0.62
    pts[11], pts[12] = sh_l, sh_r
    pts[23], pts[24] = hp_l, hp_r
    pts[13] = (el_x, 0.25, 0.0)
    pts[14] = (el_x, 0.25, 0.0)
    pts[15] = (wr_x, wrist_y, 0.0)
    pts[16] = (wr_x, wrist_y, 0.0)

    world = [(0.0, 0.0, 0.0) for _ in range(33)]
    half = 0.05 if side else 0.20
    world[11] = (-half, 0.0, 0.0)
    world[12] = (half, 0.0, 0.0)
    world[23] = (-half, 0.4, 0.0)
    world[24] = (half, 0.4, 0.0)
    world[15] = (0.0, -0.3, 0.0)
    world[16] = (0.0, -0.3, 0.0)
    return pts, world


def make_stream(bpm: float = 110, depth_cm: float = 5.6, seconds: float = 10.0, fps: int = 15):
    """Синтетический сигнал кистей: нормальные компрессии с заданным темпом."""
    amp = depth_cm / 100 / 2          # половина размаха, метры
    freq = bpm / 60.0
    out = []
    for i in range(int(seconds * fps)):
        t = i / fps
        out.append((t, amp * math.sin(2 * math.pi * freq * t)))
    return out


# ------------------------------------------------------------------ геометрия
def test_angle_deg():
    assert angle_deg((0, 0, 0), (1, 0, 0), (2, 0, 0)) == pytest.approx(180.0, abs=0.1)
    assert angle_deg((0, 0, 0), (1, 0, 0), (1, 1, 0)) == pytest.approx(90.0, abs=0.1)


def test_ideal_pose_all_checks_pass():
    fm = frame_metrics(*make_pose())
    assert fm["arms_straight"] is True
    assert fm["arms_vertical"] is True
    assert fm["hands_together"] is True
    assert fm["hands_on_midline"] is True
    assert fm["side_view"] is True
    assert fm["hands_together_cm"] <= HANDS_TOGETHER_CM


def test_bent_arms_detected():
    fm = frame_metrics(*make_pose(arms_straight=False))
    assert fm["arms_straight"] is False
    assert fm["arm_right_deg"] < 160


def test_front_view_detected():
    fm = frame_metrics(*make_pose(side=False))
    assert fm["side_view"] is False
    assert fm["side_ratio"] >= 0.45


def test_no_world_landmarks_gives_no_cm():
    fm = frame_metrics(make_pose()[0], None)
    assert fm["hands_together_cm"] is None
    assert fm["wrists_y"] is None
    assert fm["arms_straight"] is True


# ------------------------------------------------------------------ темп и глубина
def test_tempo_and_depth_from_synthetic_signal():
    agg = SessionAggregator()
    for t, y in make_stream(bpm=110, depth_cm=5.6):
        agg.add_frame(t, {"pose": True, "wrists_y": y, "arms_straight": True,
                          "arms_vertical": True, "hands_together": True,
                          "hands_on_midline": True, "side_view": True})
    live = agg.snapshot()
    assert live["tempo_bpm"] == pytest.approx(110, abs=12)
    assert live["depth_cm"] == pytest.approx(5.6, abs=1.5)
    assert live["rhythm_cv"] is not None and live["rhythm_cv"] < 0.15


def test_slow_tempo_detected():
    agg = SessionAggregator()
    for t, y in make_stream(bpm=70, depth_cm=5.0):
        agg.add_frame(t, {"pose": True, "wrists_y": y})
    assert agg.snapshot()["tempo_bpm"] == pytest.approx(70, abs=8)


def test_aggregator_counts_percentages():
    agg = SessionAggregator()
    for i in range(10):
        agg.add_frame(float(i), {"pose": True, "arms_straight": i < 9,
                                 "arms_vertical": True, "hands_together": i < 5})
    agg.add_frame(11.0, {"pose": False})
    snap = agg.snapshot()
    assert snap["frames_total"] == 11
    assert snap["frames_with_pose"] == 10
    assert snap["arms_straight_pct"] == pytest.approx(90.0)
    assert snap["hands_together_pct"] == pytest.approx(50.0)


def test_empty_aggregator_gives_none():
    snap = SessionAggregator().snapshot()
    assert snap["frames_with_pose"] == 0
    assert snap["arms_straight_pct"] is None
    assert snap["tempo_bpm"] is None


# ------------------------------------------------------------------ оценка
def test_good_technique_passes():
    verdict = score_from_aggregates({
        "frames_with_pose": 400, "tempo_bpm": 110.0, "depth_cm": 5.6,
        "arms_straight_pct": 96.0, "arms_vertical_pct": 94.0,
        "hands_together_pct": 92.0,
    })
    assert verdict["status"] == "done"
    assert verdict["score"] >= 90
    assert verdict["verdict"] == "pass"


def test_bad_technique_fails():
    verdict = score_from_aggregates({
        "frames_with_pose": 400, "tempo_bpm": 160.0, "depth_cm": 2.0,
        "arms_straight_pct": 10.0, "arms_vertical_pct": 20.0,
        "hands_together_pct": 5.0,
    })
    assert verdict["verdict"] == "fail"
    assert verdict["score"] < 30
    assert "темп" in verdict["comment"]


def test_no_pose_in_frame():
    verdict = score_from_aggregates({"frames_with_pose": 0})
    assert verdict["status"] == "failed"
    assert verdict["score"] is None


# ------------------------------------------------------------------ очередь и слоты
def test_single_slot_queue_order():
    slots = SlotManager(max_sessions=1, queue_limit=5, heartbeat_timeout=60)
    first = slots.join(1)
    assert first["status"] == ACTIVE

    second = slots.join(2)
    assert second["status"] == WAITING
    assert second["position"] == 1

    third = slots.join(3)
    assert third["position"] == 2

    slots.leave(1)
    assert slots.status(2)["status"] == ACTIVE
    assert slots.status(3)["position"] == 1


def test_rejoin_keeps_status():
    slots = SlotManager(max_sessions=1, queue_limit=5, heartbeat_timeout=60)
    slots.join(1)
    slots.join(2)
    again = slots.join(2)
    assert again["status"] == WAITING
    assert again["position"] == 1
    assert slots.stats()["waiting"] == 1


def test_queue_limit():
    slots = SlotManager(max_sessions=1, queue_limit=2, heartbeat_timeout=60)
    slots.join(1)
    slots.join(2)
    slots.join(3)
    with pytest.raises(QueueFullError):
        slots.join(4)


def test_heartbeat_expires_and_promotes():
    slots = SlotManager(max_sessions=1, queue_limit=5, heartbeat_timeout=0.05)
    slots.join(1)
    slots.join(2)
    time.sleep(0.12)
    expired = slots.sweep()
    assert expired == [1]
    assert slots.status(2)["status"] == ACTIVE


def test_frame_keeps_slot_alive():
    slots = SlotManager(max_sessions=1, queue_limit=5, heartbeat_timeout=0.08)
    slots.join(1)
    for _ in range(5):
        time.sleep(0.04)
        slots.on_frame_submitted(1)
    assert slots.sweep() == []
    assert slots.status(1)["status"] == ACTIVE


def test_metrics_go_to_session_summary():
    slots = SlotManager(max_sessions=1, queue_limit=5, heartbeat_timeout=60)
    slots.join(7)
    slots.add_metrics(7, 0.0, {"pose": True, "arms_straight": True, "wrists_y": 0.0})
    summary = slots.leave(7)
    assert summary["frames_with_pose"] == 1
    assert summary["arms_straight_pct"] == 100.0
    assert summary["status"] == "done"


def test_leave_unknown_session():
    assert SlotManager().leave(999) is None


# ------------------------------------------------------------------ приём кадра
def test_decode_jpeg_bytes():
    import base64

    raw = b"\xff\xd8\xff\xe0" + b"0" * 100
    assert _decode_image(base64.b64encode(raw).decode()) == raw
    assert _decode_image("data:image/jpeg;base64," + base64.b64encode(raw).decode()) == raw


def test_decode_rejects_non_jpeg():
    import base64

    with pytest.raises(ValueError):
        _decode_image(base64.b64encode(b"%PDF-1.4").decode())


def test_decode_rejects_empty():
    with pytest.raises(ValueError):
        _decode_image("")


# ------------------------------------------------------------------ выключенный режим
def test_disabled_service_refuses_frames():
    """VISION_ENABLED=0 (по умолчанию): кадры не принимаются, внятная ошибка."""
    from backend.app.vision.service import VisionDisabledError, get_service

    service = get_service()
    assert service.stats()["enabled"] is False
    with pytest.raises(VisionDisabledError):
        service.join(1)
    with pytest.raises(VisionDisabledError):
        service.push_frame(1, "data:image/jpeg;base64,AAAA")
