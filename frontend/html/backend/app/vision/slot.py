"""Слоты видеоанализа: одна станция работает, остальные ждут в очереди.

Правила (согласованы с постановкой задачи):
  * одновременно обрабатывается MAX_VIDEO_SESSIONS попыток (на 2 ГБ сервере — одна);
  * остальные становятся в очередь FIFO: кто раньше встал, тот раньше прошёл;
  * очередь ограничена QUEUE_LIMIT — дальше честно отказываем, а не копим;
  * если кадры не приходят HEARTBEAT_TIMEOUT секунд (закрыли браузер, пропала
    сеть), слот освобождается сам, очередь двигается.

Всё под одним замком: FastAPI обслуживает запросы в разных потоках.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .geometry import SessionAggregator

WAITING = "waiting"
ACTIVE = "active"
EXPIRED = "expired"
DONE = "done"


class QueueFullError(RuntimeError):
    """Очередь переполнена — новую сессию принимать некуда."""


@dataclass
class Session:
    attempt_id: int
    status: str = WAITING
    joined_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    last_seen: float = field(default_factory=time.monotonic)
    frames_submitted: int = 0
    frames_processed: int = 0
    agg: SessionAggregator = field(default_factory=SessionAggregator)
    queue_wait_s: float = 0.0


class SlotManager:
    def __init__(self, max_sessions: int = 1, queue_limit: int = 20,
                 heartbeat_timeout: float = 20.0, session_eta_s: float = 240.0) -> None:
        self.max_sessions = max(1, int(max_sessions))
        self.queue_limit = max(0, int(queue_limit))
        self.heartbeat_timeout = float(heartbeat_timeout)
        self.session_eta_s = float(session_eta_s)
        self._lock = threading.RLock()
        self._sessions: dict[int, Session] = {}
        self._waiting: list[int] = []
        self.expired_total = 0

    # ---------------------------------------------------------------- служебное
    def _active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == ACTIVE)

    def _promote(self) -> None:
        """Заполнить свободные слоты из очереди."""
        while self._waiting and self._active_count() < self.max_sessions:
            attempt_id = self._waiting.pop(0)
            session = self._sessions.get(attempt_id)
            if session is None or session.status != WAITING:
                continue
            session.status = ACTIVE
            session.started_at = time.monotonic()
            session.last_seen = session.started_at
            session.queue_wait_s = round(session.started_at - session.joined_at, 1)

    def _info(self, session: Session) -> dict[str, Any]:
        position = None
        if session.status == WAITING and session.attempt_id in self._waiting:
            position = self._waiting.index(session.attempt_id) + 1
        eta = None
        if position is not None:
            # сколько ждать: перед вами position-1 человек, каждый ≈ длина станции
            eta = int((position - 1) * self.session_eta_s / self.max_sessions + self.session_eta_s * 0.5)
        return {
            "status": session.status,
            "position": position,
            "queue_length": len(self._waiting),
            "eta_sec": eta,
            "active": self._active_count(),
            "max_sessions": self.max_sessions,
            "frames_submitted": session.frames_submitted,
            "frames_processed": session.frames_processed,
            "queue_wait_s": round(session.queue_wait_s, 1),
        }

    # ---------------------------------------------------------------- API
    def join(self, attempt_id: int) -> dict[str, Any]:
        """Встать в очередь или сразу получить слот (повторный вход — тот же статус)."""
        with self._lock:
            self.sweep()
            session = self._sessions.get(attempt_id)
            if session is None:
                if (len(self._waiting) >= self.queue_limit
                        and self._active_count() >= self.max_sessions):
                    raise QueueFullError(
                        f"Очередь заполнена ({self.queue_limit} человек), попробуйте позже"
                    )
                session = Session(attempt_id=attempt_id)
                if self._active_count() < self.max_sessions:
                    session.status = ACTIVE
                    session.started_at = time.monotonic()
                else:
                    self._waiting.append(attempt_id)
                self._sessions[attempt_id] = session
            return self._info(session)

    def status(self, attempt_id: int) -> dict[str, Any] | None:
        with self._lock:
            self.sweep()
            session = self._sessions.get(attempt_id)
            return self._info(session) if session else None

    def touch(self, attempt_id: int) -> bool:
        """Отметить активность сессии (пришёл кадр или heartbeat)."""
        with self._lock:
            session = self._sessions.get(attempt_id)
            if session is None:
                return False
            session.last_seen = time.monotonic()
            return session.status == ACTIVE

    def on_frame_submitted(self, attempt_id: int) -> None:
        with self._lock:
            session = self._sessions.get(attempt_id)
            if session is not None:
                session.frames_submitted += 1
                session.last_seen = time.monotonic()

    def add_metrics(self, attempt_id: int, t: float, fm: dict[str, Any]) -> None:
        with self._lock:
            session = self._sessions.get(attempt_id)
            if session is None:
                return
            session.agg.add_frame(t, fm)
            session.frames_processed += 1
            session.last_seen = time.monotonic()

    def snapshot(self, attempt_id: int) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(attempt_id)
            if session is None:
                return None
            return session.agg.snapshot()

    def leave(self, attempt_id: int) -> dict[str, Any] | None:
        """Завершить сессию и получить итоговые показатели."""
        with self._lock:
            session = self._sessions.pop(attempt_id, None)
            if session is None:
                return None
            if attempt_id in self._waiting:
                self._waiting.remove(attempt_id)
            summary = session.agg.summary()
            summary["status"] = DONE if session.status == ACTIVE else "cancelled"
            summary["queue_wait_s"] = round(session.queue_wait_s, 1)
            self._promote()
            return summary

    def sweep(self) -> list[int]:
        """Освободить слоты, из которых давно не приходило кадров."""
        now = time.monotonic()
        expired: list[int] = []
        for session in list(self._sessions.values()):
            if session.status == ACTIVE and now - session.last_seen > self.heartbeat_timeout:
                session.status = EXPIRED
                self._sessions.pop(session.attempt_id, None)
                expired.append(session.attempt_id)
                self.expired_total += 1
        if expired:
            self._promote()
        return expired

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self._active_count(),
                "waiting": len(self._waiting),
                "max_sessions": self.max_sessions,
                "queue_limit": self.queue_limit,
                "expired_total": self.expired_total,
            }
