"""Видеоанализ техники: MediaPipe Pose на сервере + очередь на одну станцию.

Модули:
    geometry.py  — математика по точкам скелета (без внешних зависимостей)
    worker.py    — отдельный процесс с моделью MediaPipe
    slot.py      — слоты и очередь FIFO с watchdog
    service.py   — связка всего + сохранение в попытку
    scoring.py   — балл и вердикт по агрегатам
"""
from .service import VisionDisabledError, get_service  # noqa: F401
from .slot import QueueFullError  # noqa: F401
