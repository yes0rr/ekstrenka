"""Модели БД: пользователи, логи, испытания, вопросы, попытки, ответы."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    teacher = "teacher"  # проводящий испытание
    student = "student"  # учащийся


class Mode(str, enum.Enum):
    training = "training"  # режим обучения (с подсказками и разбором)
    testing = "testing"  # режим тестирования (без подсказок)


class SubjectType(str, enum.Enum):
    human = "human"  # испытание на человеке
    imitation = "imitation"  # имитация предметами


class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    finished = "finished"
    aborted = "aborted"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.student.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active/blocked
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tests: Mapped[list["Test"]] = relationship(back_populates="author")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="student")

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.teacher.value


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-строка
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)

    user: Mapped["User | None"] = relationship()


class Test(Base):
    """Испытание (набор вопросов/заданий), создаётся преподавателем."""
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default=Mode.testing.value, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(20), default=SubjectType.human.value, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    use_camera: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_mic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # критерии оценки (описание алгоритма проверки, по ним потом пойдёт нейросеть)
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    author: Mapped["User"] = relationship(back_populates="tests")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="Question.order_index"
    )
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="test", cascade="all, delete-orphan")

    @property
    def max_score(self) -> float:
        return float(sum(q.points for q in self.questions))


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="single", nullable=False)  # single/multiple/text
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: список вариантов
    correct: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: правильные ответы
    points: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)  # подсказка для режима обучения

    test: Mapped["Test"] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class Attempt(Base):
    """Попытка прохождения испытания конкретным учащимся."""
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AttemptStatus.in_progress.value, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default=Mode.testing.value, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(20), default=SubjectType.human.value, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # медиа: сейчас только метаданные (камера/микрофон включались, сколько секунд, заметка)
    camera_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mic_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    media_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # проверка «нейросетью» — пока заглушка
    neural_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    neural_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    neural_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # видеоанализ техники: статус + все показатели одним JSON
    # (off — не запускался, done — есть результат, expired — сессия оборвалась)
    vision_status: Mapped[str] = mapped_column(String(20), default="off", nullable=False)
    vision_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ручной ввод оценки преподавателем
    manual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    test: Mapped["Test"] = relationship(back_populates="attempts")
    student: Mapped["User"] = relationship(back_populates="attempts")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )

    @property
    def final_score(self) -> float:
        return self.manual_score if self.manual_score is not None else self.score


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: выбранные/введённые значения
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    awarded_points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(back_populates="answers")
