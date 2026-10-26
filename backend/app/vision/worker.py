"""Отдельный процесс с моделью MediaPipe Pose.

Почему процесс, а не поток:
  * MediaPipe в режиме VIDEO однопоточный и требует монотонно растущих меток
    времени — на каждый видеопоток нужен свой экземпляр модели;
  * GIL: инференс в потоке душил бы FastAPI;
  * если модель упадёт (битый кадр, нехватка памяти), падает только воркер,
    а сайт продолжает работать — воркер поднимается заново.

Обмен: multiprocessing.Queue. Очередь кадров ОГРАНИЧЕНА (FRAME_BUFFER):
при переполнении выбрасываем самый старый кадр, иначе при 15 fps на слабом
сервере очередь растёт быстрее, чем обрабатывается, и задержка уезжает в минуты.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from queue import Empty, Full
from typing import Any

log = logging.getLogger(__name__)

# сообщения воркера: (kind, attempt_id | None, seq | None, payload)
Kind = str


def _pose_loop(in_q: "mp.Queue", out_q: "mp.Queue", model_path: str) -> None:
    """Тело процесса-воркера. Импорты внутри — чтобы приложение на старте
    не требовало mediapipe/opencv, если видеоанализ выключен."""
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        from .geometry import frame_metrics
    except Exception as exc:  # noqa: BLE001
        out_q.put(("error", None, None, f"зависимости не установлены: {exc}"))
        return

    try:
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
        )
        landmarker = mp_vision.PoseLandmarker.create_from_options(options)
    except Exception as exc:  # noqa: BLE001
        out_q.put(("error", None, None, f"модель не загрузилась ({model_path}): {exc}"))
        return

    out_q.put(("ready", None, None, None))
    last_ts = 0

    while True:
        try:
            item = in_q.get(timeout=1.0)
        except Empty:
            continue
        if item is None:          # команда остановки
            break

        attempt_id, seq, jpeg, ts_ms = item
        try:
            buf = np.frombuffer(jpeg, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("кадр не декодируется (ожидается JPEG)")
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # метка времени должна строго расти, иначе MediaPipe ругается
            ts = int(max(int(ts_ms or 0), last_ts + 1))
            last_ts = ts

            res = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
            )
            if not res.pose_landmarks:
                fm: dict[str, Any] = {"pose": False}
            else:
                # в mediapipe ≥1.0 поле называется pose_world_landmarks,
                # в старых сборках — world_landmarks; поддерживаем оба
                world_list = getattr(res, "pose_world_landmarks", None) or getattr(res, "world_landmarks", None)
                world = world_list[0] if world_list else None
                fm = frame_metrics(res.pose_landmarks[0], world)
                fm["pose"] = True
            out_q.put(("metrics", attempt_id, seq, fm))
        except Exception as exc:  # noqa: BLE001
            out_q.put(("error", attempt_id, seq, str(exc)))

    try:
        landmarker.close()
    except Exception:  # noqa: BLE001
        pass


class PoseRuntime:
    """Управление процессом-воркером из приложения."""

    def __init__(self, model_path: str, frame_buffer: int = 30) -> None:
        self.model_path = model_path
        self.frame_buffer = frame_buffer
        self._in: "mp.Queue | None" = None
        self._out: "mp.Queue | None" = None
        self._proc: "mp.Process | None" = None
        self.dropped = 0
        self.last_error: str | None = None

    # ---------------------------------------------------------------- жизненный цикл
    @property
    def alive(self) -> bool:
        return bool(self._proc and self._proc.is_alive())

    def start(self) -> None:
        if self.alive:
            return
        ctx = mp.get_context("spawn")   # spawn: безопаснее с uvicorn
        self._in = ctx.Queue(maxsize=self.frame_buffer)
        self._out = ctx.Queue()
        self._proc = ctx.Process(
            target=_pose_loop,
            args=(self._in, self._out, self.model_path),
            daemon=True,
            name="pose-worker",
        )
        self._proc.start()
        log.info("воркер видеоанализа запущен (pid=%s, модель=%s)",
                 self._proc.pid, self.model_path)

    def stop(self) -> None:
        if self._in is not None:
            try:
                self._in.put_nowait(None)
            except Full:
                pass
        if self._proc is not None:
            self._proc.join(timeout=3)
            if self._proc.is_alive():
                self._proc.terminate()
        self._proc = self._in = None
        self._out = None

    # ---------------------------------------------------------------- кадры
    def submit(self, attempt_id: int, seq: int, jpeg: bytes, ts_ms: int) -> bool:
        """Положить кадр в очередь воркера. False — если очередь переполнена."""
        if not self.alive or self._in is None:
            return False
        item = (attempt_id, seq, jpeg, ts_ms)
        try:
            self._in.put_nowait(item)
            return True
        except Full:
            # выбрасываем самый старый кадр и пробуем ещё раз: свежий важнее
            try:
                self._in.get_nowait()
                self.dropped += 1
            except Empty:
                pass
            try:
                self._in.put_nowait(item)
                return True
            except Full:
                self.dropped += 1
                return False

    # ---------------------------------------------------------------- результаты
    def poll(self, limit: int = 50) -> list[tuple[Kind, int | None, int | None, Any]]:
        """Забрать до limit готовых сообщений, не блокируясь."""
        out: list[tuple[Kind, int | None, int | None, Any]] = []
        if self._out is None:
            return out
        for _ in range(limit):
            try:
                out.append(self._out.get_nowait())
            except Empty:
                break
            except (EOFError, OSError):
                break
        return out
