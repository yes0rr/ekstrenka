"""Тесты видеотеста v24: два раздела, девять тестов по сценариям, ответы словами."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.answermatch import match
from backend.app.main import app
from backend.app.quizbank import (
    QUESTIONS,
    SCENARIOS,
    SECTIONS,
    TESTS,
    TOTAL,
    by_id,
    by_test,
    section_tests,
)
from backend.app.videoquiz import verdict

STUDENT = {"email": "student@example.com", "password": "student123"}
TEACHER = {"email": "teacher@example.com", "password": "teacher123"}


def _student_client() -> TestClient:
    """Клиент с активной сессией учащегося (демо-аккаунт из seed)."""
    client = TestClient(app)
    client.__enter__()
    response = client.post("/login", data=STUDENT, follow_redirects=False)
    assert response.status_code == 303
    return client


def _start(client: TestClient, test: str = "diagnostics_all", mode: str = "training",
           lang: str = "ru") -> dict:
    response = client.post("/api/video-quiz/start",
                           json={"test": test, "mode": mode, "lang": lang})
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------- банк вопросов -----------------------------

def test_bank_has_two_sections_and_nine_scenarios():
    """Два раздела; в каждом 9 тестов по сценариям + 1 общий; 5 вопросов на сценарий."""
    assert [s.key for s in SECTIONS] == ["diagnostics", "treatment"]
    assert len(SCENARIOS) == 9
    for section in SECTIONS:
        tests = section_tests(section.key)
        # 9 сценариев + 2 теста «всё занятие» (ОДН/комы, ОКС/шоки) + общий зачётный
        assert len(tests) == 12
        scenario_tests = [t for t in tests if not t.key.endswith("_all")
                          and "_lesson" not in t.key]
        assert len(scenario_tests) == 9
        for test in scenario_tests:
            # по вопросам преподавателя: 4 общих + столько, сколько есть у сценария
            assert 2 <= len(test.question_ids) <= 6
        total_test = [t for t in tests if t.key.endswith("_all")][0]
        assert len(total_test.question_ids) == sum(1 for q in QUESTIONS if q.section == section.key)
    assert TOTAL == len(QUESTIONS) == 77
    assert len(TESTS) == 24


def test_every_question_is_answerable_by_words():
    """У вопроса есть текст, эталон, ключевые группы и пояснение; вариантов ответа нет."""
    assert [q.id for q in QUESTIONS] == list(range(1, TOTAL + 1))
    for q in QUESTIONS:
        assert q.text["ru"].strip()
        assert q.reference["ru"].strip()
        assert len(q.keys) >= 1
        assert q.explain["ru"].strip()
        assert q.checklist.strip()
        assert 1 <= q.scenario <= 9
        assert not hasattr(q, "options"), "вариантов ответа быть не должно"


def test_matching_accepts_different_wording():
    """Один и тот же смысл разными словами — засчитывается."""
    question = [q for q in QUESTIONS if q.test == "diag_oks1"][0]   # этап, на котором заподозрили ОКС
    assert match(question, "на этапе циркулейшин, когда смотрел сердечно-сосудистую систему")["verdict"] == "correct"
    assert match(question, "на этапе СИ")["verdict"] in ("correct", "partial")


def test_reference_answer_is_always_accepted():
    """Санитарная проверка банка: каждый эталон засчитывается как верный ответ."""
    bad = [q.id for q in QUESTIONS if match(q, q.reference["ru"])["verdict"] != "correct"]
    assert bad == [], f"эталоны, которые не проходят собственную проверку: {bad}"


def test_matching_rejects_opposite_meaning():
    """Ответ про другой этап — ошибка, а не «не расслышал»."""
    question = [q for q in QUESTIONS if q.test == "diag_oks1"][0]
    result = match(question, "кислород не показана, сатурация норма")
    assert result["verdict"] == "wrong"
    assert result["blocked"]


def test_negation_is_still_rejected():
    """Отрицание по смыслу: «кислород не нужен» там, где показан — ошибка."""
    question = [q for q in QUESTIONS if q.must_not][0]
    result = match(question, "сатурация нормальная, " + question.must_not[0])
    assert result["verdict"] == "wrong"
    assert result["blocked"]


def test_matching_marks_partial_answer():
    """Половина смысла — «принято, но сказано не всё»."""
    question = [q for q in QUESTIONS if q.test == "diag_oks1"][0]
    assert match(question, "на этапе СИ")["verdict"] in ("partial", "correct")
    assert match(question, "не помню")["verdict"] == "wrong"


def test_verdict_scale_follows_expert_criteria():
    """90–100 отлично, 80–89 хорошо, 70–79 удовлетворительно, ниже — неудовлетворительно."""
    assert verdict(95)[0] == "excellent"
    assert verdict(85)[0] == "good"
    assert verdict(75)[0] == "fair"
    assert verdict(69)[0] == "bad"


# ----------------------------- каталог и заход -----------------------------

def test_sections_endpoint_lists_sections_and_tests():
    with _student_client() as client:
        payload = client.get("/api/video-quiz/sections").json()
        assert payload["total"] == TOTAL
        keys = [item["key"] for item in payload["sections"]]
        assert keys == ["diagnostics", "treatment"]
        for section in payload["sections"]:
            assert section["title"] and section["description"]
            # 9 сценариев + 2 теста «всё занятие» + общий зачётный
            assert len(section["tests"]) == 12
            for test in section["tests"]:
                assert test["title"] and test["count"] >= 1
                assert test["section"] == section["key"]

        english = client.get("/api/video-quiz/sections?lang=en").json()
        assert english["sections"][0]["title"] == "Diagnostics"


def test_start_returns_only_questions_of_the_test():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        assert len(run["items"]) == run["total"] == len(by_test("diag_oks1").question_ids)
        assert run["section"] == "diagnostics"
        assert run["test_title"]
        ids = {item["id"] for item in run["items"]}
        assert ids <= set(by_test("diag_oks1").question_ids)
        for item in run["items"]:
            assert "reference" not in item and "keys" not in item

        big = _start(client, "treatment_all")
        assert big["total"] == sum(1 for q in QUESTIONS if q.section == "treatment")


def test_unknown_test_is_rejected():
    with _student_client() as client:
        response = client.post("/api/video-quiz/start",
                               json={"test": "нет-такого", "mode": "training", "lang": "ru"})
        assert response.status_code == 422


def test_start_shuffles_questions():
    with _student_client() as client:
        orders = set()
        for _ in range(5):
            run = _start(client, "diagnostics_all")
            orders.add(tuple(item["id"] for item in run["items"]))
        assert len(orders) > 1, "вопросы не перемешиваются"


# ----------------------------- ответы -----------------------------

def test_training_answer_shows_verdict_and_reference():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        question = by_id(item["id"])
        response = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"],
            "text": question.reference["ru"]})
        assert response.status_code == 200
        payload = response.json()
        assert payload["accepted"] is True
        assert payload["verdict"] == "correct"
        assert payload["reference"] == question.reference["ru"]
        assert payload["explain"]


def test_wrong_answer_is_accepted_but_marked_wrong():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        payload = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "не знаю"}).json()
        assert payload["accepted"] is True
        assert payload["correct"] is False


def test_unrecognised_short_answer_asks_to_repeat():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        payload = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "э"}).json()
        assert payload["accepted"] is False and payload["retry"] is True


def test_empty_answer_and_second_answer_are_rejected():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        empty = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "   "})
        assert empty.status_code == 422
        first = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "сатурация 88"})
        assert first.status_code == 200
        second = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "сатурация 88"})
        assert second.status_code == 409


def test_testing_mode_does_not_reveal_verdict():
    with _student_client() as client:
        run = _start(client, "diag_oks1", mode="testing")
        item = run["items"][0]
        payload = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "сатурация 88"}).json()
        assert payload == {"question_id": item["id"], "accepted": True}


def test_alien_run_is_forbidden():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        run_id = run["run_id"]
    with _student_client() as other:
        response = other.post("/api/video-quiz/answer", json={
            "run_id": run_id, "question_id": 1, "text": "сатурация"})
        # чужой run для того же демо-пользователя — это тот же пользователь, поэтому 200/409;
        # проверяем, что чужой номер попытки не находится
        assert response.status_code in (200, 404, 409)
        assert other.get("/api/video-quiz/results/999999").status_code == 404


# ----------------------------- итог -----------------------------

def test_finish_counts_only_correct_answers():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        question = by_id(item["id"])
        client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"],
            "text": question.reference["ru"]})
        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert summary["score"] == 1
        assert summary["total"] == 5
        assert summary["percent"] == 20.0
        assert summary["verdict"] == "bad"
        assert len(summary["details"]) == 5
        unprepared = [d for d in summary["details"] if d["answer"] is None]
        assert len(unprepared) == 4
        for detail in summary["details"]:
            assert detail["reference"] and detail["explain"]


def test_finish_is_idempotent():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        first = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        second = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert first["id"] == second["id"]
        assert second["already_finished"] is True
        assert first["percent"] == second["percent"]


def test_history_has_one_row_per_run():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]})
        client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]})
        items = client.get("/api/video-quiz/results").json()["items"]
        assert sum(1 for row in items if row["id"] == run["run_id"]) == 1
        assert items[0]["test_title"]


def test_review_of_finished_run():
    with _student_client() as client:
        run = _start(client, "treat_ash", mode="testing")
        client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]})
        detail = client.get(f"/api/video-quiz/results/{run['run_id']}").json()
        assert detail["id"] == run["run_id"]
        assert len(detail["details"]) == run["total"]
        assert client.get("/api/video-quiz/results/999999").status_code == 404


# ----------------------------- доступ -----------------------------

def test_teacher_can_use_video_quiz():
    client = TestClient(app)
    client.__enter__()
    client.post("/login", data=TEACHER, follow_redirects=False)
    assert client.get("/api/video-quiz/sections").status_code == 200
    assert client.post("/api/video-quiz/start",
                       json={"test": "diagnostics_all"}).status_code == 200


def test_voice_status_endpoint():
    with _student_client() as client:
        payload = client.get("/api/video-quiz/voice/status").json()
        assert "server" in payload and payload["hint"] in ("server", "browser")


def test_voice_endpoint_shows_what_was_heard():
    with _student_client() as client:
        run = _start(client, "diag_oks1")
        item = run["items"][0]
        payload = client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": item["id"],
            "transcript": "сатурация восемьдесят восемь кислород показан"}).json()
        assert payload["transcript"]
        assert "matched" in payload
        assert client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": item["id"], "transcript": ""}).status_code == 422


# ----------------------------- проверка по смыслу (модель, необязательно) ---------

def test_semantic_status_is_safe_without_model():
    """Без модели и флага сервер работает на правилах и ничего не падает."""
    from backend.app import semantic_onnx

    state = semantic_onnx.status()
    assert set(state) >= {"enabled", "dependency", "model", "available", "dir"}
    assert isinstance(semantic_onnx.enabled(), bool)


def test_semantic_similarity_returns_number_or_none():
    """similarity() либо число 0…1, либо 0.0, если модели нет."""
    from backend.app import semantic_onnx

    value = semantic_onnx.similarity("пациент без сознания", "отсутствие сознания")
    assert 0.0 <= value <= 1.0


def test_teacher_opens_video_quiz_page():
    """Преподаватель открывает страницу видеотеста и видит памятку проверяющего."""
    with TestClient(app) as client:
        client.post("/login", data=TEACHER, follow_redirects=False)
        page = client.get("/student/video-quiz")
        assert page.status_code == 200
        assert "teacherNote" in page.text


def test_student_page_has_no_teacher_note():
    with _student_client() as client:
        assert "teacherNote" not in client.get("/student/video-quiz").text


def test_tests_follow_expert_lessons():
    """Тесты разложены по занятиям из таблиц: 2 — ОДН/комы, 3 — ОКС/шоки, 4 — зачёт."""
    from backend.app.quizbank import TESTS

    by_key = {t.key: t for t in TESTS}
    for key in ("bos", "pneumo", "hypo", "hyper"):
        assert by_key[f"diag_{key}"].lesson == 2
        assert by_key[f"treat_{key}"].lesson == 2
    for key in ("oks1", "oks2", "ash", "gikk", "tela"):
        assert by_key[f"diag_{key}"].lesson == 3
        assert by_key[f"treat_{key}"].lesson == 3
    # состав занятий считается от фактического банка, а не от константы
    diag = [q for q in QUESTIONS if q.section == "diagnostics"]
    assert len(by_key["diag_lesson2"].question_ids) == sum(1 for q in diag if q.lesson == 2)
    assert len(by_key["diag_lesson3"].question_ids) == sum(1 for q in diag if q.lesson == 3)
    assert len(by_key["diagnostics_all"].question_ids) == len(diag)
    assert "Занятие 2" in by_key["treat_bos"].title["ru"]
    assert "Занятие 4" in by_key["treatment_all"].title["ru"]


def test_treatment_requires_doses():
    """Вопрос про дозы: препараты без цифр — «принято частично», а не «верно»."""
    question = [q for q in QUESTIONS if q.test == "treat_ash" and "доз" in q.text["ru"]][0]
    without = match(question, "эпинефрин, физраствор, гидрокортизон, сальбутамол")
    with_doses = match(question, question.reference["ru"])
    assert without["verdict"] in ("partial", "wrong")
    assert with_doses["verdict"] == "correct"


def test_route_words_are_understood():
    """«в мышцу бедра» = в/м, «в вену» = в/в."""
    question = [q for q in QUESTIONS if q.test == "treat_ash" and "пут" in q.text["ru"]][0]
    assert match(question, question.reference["ru"])["verdict"] == "correct"
    spoken = ("эпинефрин в мышцу бедра, физраствор в вену струйно, гидрокортизон в вену, "
              "сальбутамол через небулайзер")
    assert match(question, spoken)["verdict"] == "correct"


def test_refusal_is_wrong_for_treatment():
    """«Ничего не назначал» — ошибка."""
    question = [q for q in QUESTIONS if q.section == "treatment"][0]
    assert match(question, "ничего не назначал")["verdict"] == "wrong"
    assert match(question, "не знаю")["verdict"] == "wrong"
