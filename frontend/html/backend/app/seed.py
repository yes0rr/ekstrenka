"""Демо-данные: python -m app.seed"""
from __future__ import annotations

from sqlalchemy import select

from .db import init_db, session_scope
from .models import Attempt, Question, Role, Test, User
from .security import hash_password
from .services import dumps

DEMO = [
    ("teacher@example.com", "Преподаватель Демо", "teacher123", Role.teacher.value),
    ("student@example.com", "Студент Демо", "student123", Role.student.value),
]


def seed() -> None:
    with session_scope() as db:
        for email, name, password, role in DEMO:
            if db.scalar(select(User).where(User.email == email)):
                continue
            db.add(
                User(
                    email=email,
                    full_name=name,
                    password_hash=hash_password(password),
                    role=role,
                    group_name="РИ-21" if role == Role.student.value else None,
                )
            )
        db.flush()

        teacher = db.scalar(select(User).where(User.email == "teacher@example.com"))
        if teacher and not db.scalar(select(Test).where(Test.author_id == teacher.id)):
            test = Test(
                author_id=teacher.id,
                title="Базовое собеседование по предмету",
                description="Демонстрационное испытание: три вопроса, камера и микрофон включены.",
                mode="testing",
                subject_type="human",
                duration_min=10,
                use_camera=True,
                use_mic=True,
                criteria="Полнота ответа, корректность терминологии, логика изложения.",
                is_published=True,
            )
            db.add(test)
            db.flush()
            db.add_all(
                [
                    Question(
                        test_id=test.id, order_index=0, text="Что такое испытуемый объект?",
                        kind="single", options=dumps(["Человек", "Прибор", "Предмет"]),
                        correct=dumps("Человек"), points=1, hint="Речь о том, кого испытывают.",
                    ),
                    Question(
                        test_id=test.id, order_index=1,
                        text="Какие признаки относятся к имитации предметами?",
                        kind="multiple",
                        options=dumps(["Макет", "Стенд", "Живой человек"]),
                        correct=dumps(["Макет", "Стенд"]), points=2,
                        hint="Живой человек — это уже испытание на человеке.",
                    ),
                    Question(
                        test_id=test.id, order_index=2,
                        text="Опишите порядок проведения испытания.",
                        kind="text_manual", correct=None, points=3,
                        hint="Ответ проверит преподаватель.",
                    ),
                ]
            )


if __name__ == "__main__":
    init_db()
    seed()
    print("Демо-данные созданы: teacher@example.com / teacher123, student@example.com / student123")
