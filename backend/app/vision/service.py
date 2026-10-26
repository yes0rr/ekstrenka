"""Связка: слоты + воркер MediaPipe + сохранение в БД.

Один экземпляр на процесс приложения (синглтон). Если VISION_ENABLED=0 —
эндпоинты отвечают 503, воркер не запускается, mediapipe не требуется.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import threading
import time
from typing import Any

from ..config import settings
from .slot import QueueFullError, SlotManager
from .worker import PoseRuntime

log = logging.getLogger(__name__)

MAX_FRAME_BYTES = 2 * 1024 * 1024   # один кадр не больше 2 МБ


class VisionDisabledError(RuntimeError):
    """Видеоанализ выключен или модель недоступна."""


class VisionService:
    def __init__(self) -> None:
        self.slots = SlotManager(
            max_sessions=settings.max_video_sessions,
            queue_limit=settings.queue_limit,
            heartbeat_timeout=settings.heartbeat_timeout,
            session_eta_s=settings.session_eta_sec,
        )
        self._runtime: PoseRuntime | None = None
        self._drain: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.error: str | None = None
        self.started_at: float | None = None
        self.frames_dropped = 0

    # ---------------------------------------------------------------- запуск
    def start(self) -> None:
        if not settings.vision_enabled:
            log.info("видеоанализ выключен (VISION_ENABLED=0)")
            return
        with self._lock:
            if self._runtime is not None:
                return
            model_path = str(settings.pose_model_path)
            import os
            if not os.path.exists(model_path):
                self.error = (
                    f"нет файла модели: {model_path}. "
                    f"Скачайте: python tools/download_pose_model.py"
                )
                log.error(self.error)
                return
            runtime = PoseRuntime(model_path, frame_buffer=settings.frame_buffer)
            runtime.start()
            self._runtime = runtime
            self.started_at = time.time()
            self._stop.clear()
            self._drain = threading.Thread(target=self._drain_loop, daemon=True,
                                           name="pose-drain")
            self._drain.start()
            log.info("сервис видеоанализа запущен")

    def stop(self) -> None:
        self._stop.set()
        if self._runtime is not None:
            self._runtime.stop()
            self._runtime = None

    # ---------------------------------------------------------------- фон
    def _drain_loop(self) -> None:
        """Забирает результаты воркера и считает агрегаты + следит за слотами."""
        last_sweep = 0.0
        while not self._stop.is_set():
            runtime = self._runtime
            if runtime is None:
                break
            for kind, attempt_id, _seq, payload in runtime.poll():
                if kind == "ready":
                    log.info("модель MediaPipe загружена")
                elif kind == "metrics" and attempt_id is not None:
                    self.slots.add_metrics(int(attempt_id), time.monotonic(), payload)
                elif kind == "error":
                    self.error = str(payload)
                    if attempt_id is None:
                        log.error("воркер видеоанализа: %s", payload)
                    else:
                        log.warning("кадр отклонён (попытка %s): %s", attempt_id, payload)
            now = time.monotonic()
            if now - last_sweep > 5:
                expired = self.slots.sweep()
                if expired:
                    log.info("слоты освобождены по таймауту: %s", expired)
                last_sweep = now
            time.sleep(0.05)

    # ---------------------------------------------------------------- проверки
    def _require_runtime(self) -> PoseRuntime:
        if not settings.vision_enabled:
            raise VisionDisabledError("Видеоанализ выключен (VISION_ENABLED=0)")
        if self._runtime is None:
            raise VisionDisabledError(self.error or "Видеоанализ не запущен")
        return self._runtime

    # ---------------------------------------------------------------- API для роутера
    def join(self, attempt_id: int) -> dict[str, Any]:
        self._require_runtime()
        info = self.slots.join(attempt_id)
        info["result"] = self.slots.snapshot(attempt_id)
        return info

    def status(self, attempt_id: int) -> dict[str, Any] | None:
        info = self.slots.status(attempt_id)
        if info is None:
            return None
        info["result"] = self.slots.snapshot(attempt_id)
        return info

    def push_frame(self, attempt_id: int, image: str, ts_ms: int | None = None) -> dict[str, Any]:
        runtime = self._require_runtime()
        info = self.slots.status(attempt_id)
        if info is None:
            raise KeyError("Сессия видеоанализа не открыта — сначала /vision/join")
        if info["status"] != "active":
            return {"accepted": False, "reason": "waiting", **info}

        jpeg = _decode_image(image)
        seq = info["frames_submitted"] + 1
        ts = int(ts_ms if ts_ms is not None else time.monotonic() * 1000)
        ok = runtime.submit(attempt_id, seq, jpeg, ts)
        if ok:
            self.slots.on_frame_submitted(attempt_id)
        else:
            self.frames_dropped += 1
        return {
            "accepted": ok,
            "seq": seq,
            **self.slots.status(attempt_id),
            "result": self.slots.snapshot(attempt_id),
        }

    def leave(self, attempt_id: int) -> dict[str, Any] | None:
        return self.slots.leave(attempt_id)

    def persist(self, attempt, summary: dict[str, Any] | None) -> None:
        """Записать итог в попытку (вызывается из роутера, у него есть сессия БД)."""
        if summary is None:
            return
        attempt.vision_status = summary.get("status", "done")
        attempt.vision_data = json.dumps(summary, ensure_ascii=False)

    def stats(self) -> dict[str, Any]:
        data = self.slots.stats()
        data.update({
            "enabled": settings.vision_enabled,
            "worker_alive": bool(self._runtime and self._runtime.alive),
            "fps_target": settings.video_fps,
            "frames_dropped": self.frames_dropped + (self._runtime.dropped if self._runtime else 0),
            "error": self.error,
        })
        return data


def _decode_image(image: str) -> bytes:
    """Принимаем и dataURL ('data:image/jpeg;base64,...') и просто base64."""
    raw = image.strip()
    if raw.startswith("data:"):
        _, _, raw = raw.partition(",")
    try:
        data = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"кадр не в base64: {exc}") from exc
    if not data:
        raise ValueError("пустой кадр")
    if len(data) > MAX_FRAME_BYTES:
        raise ValueError(f"кадр больше {MAX_FRAME_BYTES // 1024} КБ")
    if not data.startswith(b"\xff\xd8"):   # JPEG начинается с FFD8
        raise ValueError("ожидается JPEG (data:image/jpeg;base64,...)")
    return data


_service: VisionService | None = None
_service_lock = threading.Lock()


def get_service() -> VisionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = VisionService()
        return _service
