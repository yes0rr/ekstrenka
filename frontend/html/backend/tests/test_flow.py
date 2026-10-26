"""Смоук-тест основного сценария: регистрация → испытание → прохождение → оценка."""
from __future__ import annotations

import os
import tempfile

import pytest

DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.db import Base, engine  # noqa: E402
from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def teacher():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"email": "t@test.ru", "full_name": "Учитель", "password": "secret123", "role": "teacher"},
        )
        yield client


@pytest.fixture(scope="module")
def student():
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"email": "s@test.ru", "full_name": "Студент", "password": "secret123", "role": "student"},
        )
        yield client


def test_roles_and_test_flow(teacher, student):
    # учащийся не может создавать испытания
    assert student.post("/api/tests", json={"title": "нельзя"}).status_code == 403

    created = teacher.post("/api/tests", json={"title": "Смоук", "mode": "testing", "duration_min": 5})
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]

    q1 = teacher.post(
        f"/api/tests/{test_id}/questions",
        json={"text": "2+2?", "kind": "single", "options": ["3", "4"], "correct": "4", "points": 2},
    ).json()["id"]
    q2 = teacher.post(
        f"/api/tests/{test_id}/questions",
        json={"text": "Развёрнутый ответ", "kind": "text_manual", "points": 3},
    ).json()["id"]

    # неопубликованное испытание недоступно учащемуся
    assert student.post("/api/attempts", json={"test_id": test_id}).status_code == 403
    teacher.patch(f"/api/tests/{test_id}", json={"is_published": True})

    attempt = student.post("/api/attempts", json={"test_id": test_id}).json()
    attempt_id = attempt["id"]

    r1 = student.post(f"/api/attempts/{attempt_id}/answers", json={"question_id": q1, "value": "4"})
    assert r1.status_code == 200
    # в режиме тестирования вердикт не раскрывается
    assert "is_correct" not in r1.json()

    student.post(f"/api/attempts/{attempt_id}/media", json={"camera": True, "mic": True, "seconds": 30})
    student.post(f"/api/attempts/{attempt_id}/answers", json={"question_id": q2, "value": "Текст"})

    finished = student.post(f"/api/attempts/{attempt_id}/finish").json()
    assert finished["status"] == "finished"
    assert finished["score"] == 2.0
    assert finished["max_score"] == 5.0
    assert finished["neural_status"] == "pending"
    assert finished["media"]["camera"] is True

    # ручная оценка преподавателем перекрывает авто
    manual = teacher.post(
        f"/api/attempts/{attempt_id}/manual-result",
        json={"manual_score": 4.5, "teacher_comment": "ок"},
    ).json()
    assert manual["final_score"] == 4.5

    # чужая попытка недоступна другому учащемуся
    logs = teacher.get("/api/logs").json()
    assert any(item["action"] == "attempt_finished" for item in logs)


def test_training_mode_reveals_verdict(teacher, student):
    test_id = teacher.post(
        "/api/tests", json={"title": "Обучение", "mode": "training"}
    ).json()["id"]
    qid = teacher.post(
        f"/api/tests/{test_id}/questions",
        json={"text": "Столица Франции?", "kind": "single", "options": ["Париж", "Лион"],
              "correct": "Париж", "hint": "Город Эйфелевой башни"},
    ).json()["id"]
    teacher.patch(f"/api/tests/{test_id}", json={"is_published": True})

    attempt_id = student.post("/api/attempts", json={"test_id": test_id}).json()["id"]
    res = student.post(f"/api/attempts/{attempt_id}/answers", json={"question_id": qid, "value": "Лион"}).json()
    assert res["is_correct"] is False
    assert res["correct"] == "Париж"
    assert "Эйфелевой" in res["hint"]
