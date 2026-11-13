"""Тесты видеотеста: разделы, заход, ответы (вариант/текст/голос), итог, история, доступ."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.videoquiz import QUESTIONS, RUN_SIZE, SECTIONS, TOTAL, by_id, verdict

STUDENT = {"email": "student@example.com", "password": "student123"}
TEACHER = {"email": "teacher@example.com", "password": "teacher123"}


def _student_client() -> TestClient:
    """Клиент с активной сессией учащегося (демо-аккаунт из seed)."""
    client = TestClient(app)
    client.__enter__()
    response = client.post("/login", data=STUDENT, follow_redirects=False)
    assert response.status_code == 303
    return client


def _start(client: TestClient, section: str = "all", mode: str = "training", lang: str = "ru") -> dict:
    response = client.post("/api/video-quiz/start",
                           json={"section": section, "mode": mode, "lang": lang})
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------- банк вопросов -----------------------------

def test_bank_is_consistent():
    """Двадцать вопросов, у каждого — фрагмент, варианты, верный индекс, пояснение, подсказки."""
    from backend.app.videoquiz import LANGS

    assert TOTAL == len(QUESTIONS) == 20
    assert [q.id for q in QUESTIONS] == list(range(1, TOTAL + 1))
    for q in QUESTIONS:
        assert q.clip
        assert 3 <= len(q.options["ru"]) <= 5
        assert 0 <= q.correct < len(q.options["ru"])
        assert len(set(q.options["ru"])) == len(q.options["ru"])
        assert q.checklist.startswith("п.")
        for lang in LANGS:
            assert q.title[lang] and q.question[lang] and q.explain[lang]
            assert len(q.explain[lang]) > 40
            assert len(q.triggers[lang]) == len(q.options[lang]) == len(q.options["ru"])
            assert all(option.strip() for option in q.options[lang])


def test_verdict_thresholds():
    assert verdict(100)[0] == "excellent"
    assert verdict(90)[0] == "excellent"
    assert verdict(80)[0] == "partial"
    assert verdict(70)[0] == "partial"
    assert verdict(60)[0] == "weak"
    assert verdict(50)[0] == "weak"
    assert verdict(0)[0] == "bad"


def test_verdict_suggests_link_to_guide():
    """Совет в плохом вердикте содержит слова, которые фронтенд делает ссылкой."""
    code, text = verdict(0)
    assert code == "bad"
    assert "инструкции по ЭМП" in text
    assert "emergency care guide" in verdict(0, "en")[1]


# ----------------------------- разделы и заход -----------------------------

def test_sections_catalog():
    with _student_client() as client:
        payload = client.get("/api/video-quiz/sections").json()
        assert payload["total"] == TOTAL
        keys = [item["key"] for item in payload["items"]]
        assert keys[0] == "all"
        assert len(keys) == len(SECTIONS) >= 5
        for item in payload["items"]:
            assert item["title"] and item["description"] and item["cover"]
            assert item["cover"]  # картинка карточки — постер существующего фрагмента
            assert 1 <= item["run_size"] <= RUN_SIZE
            assert item["run_size"] == item["own"], "в заходе ровно столько же, сколько в разделе"

        english = client.get("/api/video-quiz/sections?lang=en").json()
        assert english["items"][0]["title"] == "All sections"


def test_start_gives_ten_random_questions_without_answers():
    with _student_client() as client:
        first = _start(client, section="all")
        assert len(first["items"]) == RUN_SIZE
        assert first["total"] == RUN_SIZE
        assert first["run_id"] > 0
        for item in first["items"]:
            assert "correct" not in item and "explain" not in item
            assert len(item["options"]) >= 3


def test_start_shuffles_questions_and_options():
    """Каждый заход — новый набор и новый порядок; варианты тоже перемешаны."""
    with _student_client() as client:
        orders = set()
        option_orders = set()
        for _ in range(6):
            run = _start(client)
            orders.add(tuple(item["id"] for item in run["items"]))
            option_orders.add(tuple(tuple(item["options"]) for item in run["items"]))
        assert len(orders) > 1, "вопросы не перемешиваются"
        assert len(option_orders) > 1, "варианты не перемешиваются"

        # перемешаны именно варианты: у вопроса есть верный ответ в каком-то месте списка
        run = _start(client)
        item = run["items"][0]
        question = by_id(item["id"])
        assert sorted(item["options"]) == sorted(question.options["ru"])


def test_run_length_equals_section_size():
    """Заход длится столько вопросов, сколько в разделе: «3 из 20» не показываем, чужие не подмешиваем."""
    with _student_client() as client:
        run = _start(client, section="call")
        assert len(run["items"]) == 2 == run["total"]
        ids = {item["id"] for item in run["items"]}
        assert ids == {3, 11}, "в узком разделе только его вопросы"
        assert run["section"] == "call"

        wide = _start(client, section="all")
        assert len(wide["items"]) == TOTAL == RUN_SIZE == 20
        assert len({item["id"] for item in wide["items"]}) == TOTAL

        for key, size in (("exam", 6), ("cpr", 7), ("airway", 4)):
            narrow = _start(client, section=key)
            assert len(narrow["items"]) == size == narrow["total"]


def test_start_in_english():
    with _student_client() as client:
        run = _start(client, lang="en")
        assert run["lang"] == "en"
        first = run["items"][0]
        assert not any("А" <= ch <= "я" for option in first["options"] for ch in option)
        assert client.post("/api/video-quiz/start",
                           json={"section": "all", "mode": "training", "lang": "de"}).status_code == 422


# ----------------------------- ответы -----------------------------

def _correct_display_index(run: dict, item: dict) -> int:
    """Где в перемешанном списке стоит верный вариант."""
    question = by_id(item["id"])
    return item["options"].index(question.options["ru"][question.correct])


def test_training_answer_returns_verdict_in_display_indexes():
    with _student_client() as client:
        run = _start(client)
        item = run["items"][0]
        right = _correct_display_index(run, item)
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "answer": right}).json()
        assert body["correct"] is True
        assert body["correct_index"] == right  # индекс именно в том порядке, что видел учащийся
        assert body["correct_text"] == item["options"][right]  # и сам текст ответа
        assert body["explain"] and body["checklist"]

        # второй ответ на тот же вопрос не принимается: иначе после вердикта можно «передумать»
        again = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "answer": (right + 1) % len(item["options"])})
        assert again.status_code == 409

        # неверный ответ проверяем на другом вопросе того же захода
        other = run["items"][1]
        wrong = (_correct_display_index(run, other) + 1) % len(other["options"])
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": other["id"], "answer": wrong}).json()
        assert body["correct"] is False
        assert body["correct_text"] == other["options"][body["correct_index"]]


def test_testing_mode_keeps_verdict_secret():
    """Зачёт: вариантов нет, ответ текстом; сервер подтверждает приём, но не раскрывает вердикт."""
    with _student_client() as client:
        run = _start(client, section="exam", mode="testing")
        item = next(i for i in run["items"] if i["id"] == 1)
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": 1, "text": "сатурация пульсоксиметр"}).json()
        assert body == {"question_id": 1, "accepted": True, "recognised": True}


def test_text_answer_is_matched_against_options():
    """В зачёте ответ словами засчитывается, если фраза совпала с верным вариантом."""
    with _student_client() as client:
        run = _start(client, section="airway", mode="testing")  # в разделе точно есть вопрос 8
        target = next(item for item in run["items"] if item["id"] == 8)
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": 8, "text": "тридцать на два"}).json()
        assert body["accepted"] is True and body["recognised"] is True

        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        detail = next(d for d in summary["details"] if d["id"] == 8)
        assert detail["correct"] is True
        assert detail["text"] == "тридцать на два"
        assert target["options"][detail["correct_index"]] == "30:2"


def test_unrecognised_text_counts_as_wrong():
    with _student_client() as client:
        run = _start(client, mode="testing")
        item = run["items"][0]
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "не помню"}).json()
        assert body["recognised"] is False
        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert summary["score"] == 0


def test_answer_validation():
    with _student_client() as client:
        run = _start(client, section="call")
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": 999, "answer": 0}).status_code == 404  # такого вопроса нет
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": 3, "answer": 9}).status_code == 422
        assert client.post("/api/video-quiz/answer", json={
            "run_id": 999999, "question_id": 3, "answer": 0}).status_code == 404
        assert client.post("/api/video-quiz/start",
                           json={"section": "all", "mode": "hack"}).status_code == 422


# ----------------------------- итог и история -----------------------------

def test_finish_writes_exactly_one_result():
    """Главное: повторное нажатие «завершить» не добавляет запись в историю."""
    with _student_client() as client:
        before = len(client.get("/api/video-quiz/results").json()["items"])
        run = _start(client)
        for item in run["items"]:
            client.post("/api/video-quiz/answer", json={
                "run_id": run["run_id"], "question_id": item["id"],
                "answer": _correct_display_index(run, item)})

        first = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert first["score"] == RUN_SIZE
        assert first["percent"] == 100.0
        assert first["already_finished"] is False

        second = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        third = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert second["id"] == third["id"] == first["id"]
        assert second["already_finished"] is True
        assert second["percent"] == third["percent"] == 100.0

        items = client.get("/api/video-quiz/results").json()["items"]
        assert len(items) == before + 1, "запись продублировалась"
        assert items[0]["id"] == first["id"]
        assert items[0]["percent"] == 100.0


def test_answer_after_finish_is_rejected():
    with _student_client() as client:
        run = _start(client, section="call")
        client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]})
        item = run["items"][0]
        response = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "answer": 0})
        assert response.status_code == 409


def test_unanswered_questions_count_as_wrong():
    with _student_client() as client:
        run = _start(client)
        item = run["items"][0]
        client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"],
            "answer": _correct_display_index(run, item)})
        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert summary["score"] == 1
        assert summary["percent"] == 5.0
        assert len(summary["details"]) == RUN_SIZE
        missing = [d for d in summary["details"] if d["chosen"] == -1]
        assert len(missing) == RUN_SIZE - 1


def test_review_of_finished_run():
    with _student_client() as client:
        run = _start(client, mode="testing")
        client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]})
        detail = client.get(f"/api/video-quiz/results/{run['run_id']}").json()
        assert detail["id"] == run["run_id"]
        assert len(detail["details"]) == run["total"]
        for item in detail["details"]:
            assert 0 <= item["correct_index"] < len(item["options"])
        assert client.get("/api/video-quiz/results/999999").status_code == 404


def test_unfinished_run_is_not_in_history():
    with _student_client() as client:
        before = len(client.get("/api/video-quiz/results").json()["items"])
        run = _start(client)
        items = client.get("/api/video-quiz/results").json()["items"]
        assert len(items) == before
        assert client.get(f"/api/video-quiz/results/{run['run_id']}").status_code == 404


# ----------------------------- голос -----------------------------

def test_voice_endpoint_returns_display_index():
    """Голос возвращает номер варианта в том порядке, который видит учащийся."""
    with _student_client() as client:
        run = _start(client, section="airway")
        item = next(i for i in run["items"] if i["id"] == 8)
        body = client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 8, "transcript": "тридцать на два"}).json()
        assert body["option_text"] == "30:2"
        assert item["options"][body["chosen"]] == "30:2"
        assert body["confidence"] > 0

        nothing = client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 8, "transcript": "не помню"}).json()
        assert nothing["chosen"] is None


def test_voice_endpoint_validates_run():
    with _student_client() as client:
        run = _start(client, section="call")
        assert client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 999, "transcript": "тридцать на два"}).status_code == 404
        assert client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 3, "transcript": ""}).status_code == 422


def test_voice_matching_ru_and_en():
    from backend.app.voice import choose

    cases = [
        (1, "ru", "датчик на палец, сатурация", 1),
        (1, "ru", "измеряет давление тонометром", 0),
        (4, "ru", "нет сознания и нет дыхания десять секунд", 1),
        (8, "ru", "тридцать на два", 1),
        (8, "ru", "пятнадцать на два", 0),
        (13, "ru", "в течение двадцати секунд", 0),
        (17, "ru", "каждые две минуты", 0),
        (8, "en", "thirty to two", 1),
        (1, "en", "pulse oximetry saturation", 1),
    ]
    for qid, lang, text, expected in cases:
        question = by_id(qid)
        result = choose(text, question.voice_options(lang))
        assert result["chosen"] == expected, (qid, text, result)

    question = by_id(1)
    assert choose("ммм ну такое", question.voice_options("ru"))["chosen"] is None


# ----------------------------- доступ и статика -----------------------------

def test_teacher_has_no_access():
    client = TestClient(app)
    with client:
        client.post("/login", data=TEACHER, follow_redirects=False)
        assert client.get("/api/video-quiz/sections").status_code == 403
        assert client.post("/api/video-quiz/start", json={"section": "all"}).status_code == 403
        page = client.get("/student/video-quiz", follow_redirects=False)
        assert page.status_code == 303


def test_page_and_media_available():
    with _student_client() as client:
        page = client.get("/student/video-quiz")
        assert page.status_code == 200
        assert "Видеотест" in page.text
        for question in QUESTIONS:
            video = client.get(f"/static/media/quiz/{question.clip}.mp4")
            assert video.status_code == 200
            assert len(video.content) > 50_000
            assert client.get(f"/static/media/quiz/{question.clip}.jpg").status_code == 200
        assert client.get("/static/media/quiz/no_such_clip.mp4").status_code == 404


def test_translation_checker_is_clean_for_key_pages():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path.cwd()))
    from tools.check_i18n import dictionary_keys, template_phrases

    keys = dictionary_keys()
    for name in ("video_quiz.html", "emergency_help.html", "base.html"):
        phrases = template_phrases(Path("frontend/html") / name)
        missing = [p for p in phrases if p not in keys]
        assert not missing, (name, missing[:5])


# ----------------------------- нераспознанный ответ -----------------------------

def test_unrecognised_text_is_not_counted_as_wrong():
    """В зачёте непонятый ответ не засчитывается как ошибка — можно повторить."""
    with _student_client() as client:
        run = _start(client, section="all", mode="testing")
        first = client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": 1, "text": "ну такое не помню"}).json()
        assert first["retry"] is True and first["recognised"] is False

        # ответ не записался: в итогах его нет
        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        item = next(d for d in summary["details"] if d["id"] == 1)
        assert item["chosen"] == -1 and item["text"] is None

        # а после нормального ответа — засчитывается
        run2 = _start(client, section="all", mode="testing")
        body = client.post("/api/video-quiz/answer", json={
            "run_id": run2["run_id"], "question_id": 1, "text": "пульсоксиметрия"}).json()
        assert body["accepted"] is True and body["recognised"] is True
        summary = client.post("/api/video-quiz/finish", json={"run_id": run2["run_id"]}).json()
        item = next(d for d in summary["details"] if d["id"] == 1)
        assert item["correct"] is True and item["text"] == "пульсоксиметрия"


# ----------------------------- серверное распознавание -----------------------------

def test_voice_status_and_transcribe_availability():
    """Статус голоса отдаётся всегда; распознавание — 503, если модель не включена."""
    with _student_client() as client:
        status = client.get("/api/video-quiz/voice/status").json()
        assert "server" in status and "available" in status["server"]
        assert isinstance(status["server"]["available"], bool)
        assert status["hint"] in {"server", "browser"}

        if not status["server"]["available"]:
            response = client.post("/api/video-quiz/transcribe",
                                   json={"audio": "A" * 128, "lang": "ru"})
            assert response.status_code == 503


def test_speech_decoder_and_status_live_in_one_place():
    """Модуль распознавания: статус, декодирование base64 и проверка модели."""
    from backend.app import speech

    state = speech.status()
    assert set(state) >= {"enabled", "dependency", "model", "available", "model_name"}
    assert speech.decode_base64("data:audio/webm;base64," + "AA" * 50).startswith(b"\x00")
    assert speech.decode_base64("") == b""
    assert speech.decode_base64("!!!это не аудио!!!") == b""      # битый base64 не роняет сервер
    assert speech.decode_base64("AA")  # без «=» на конце тоже читается
    assert speech.encoded_size("A" * 800) == 600                  # base64 → байты звука


# ----------------------------- защита от «передумывания» -----------------------------

def test_second_answer_is_rejected():
    """Один ответ на вопрос: иначе после вердикта можно выбрать правильный вариант."""
    with _student_client() as client:
        run = _start(client)
        item = run["items"][0]
        right = _correct_display_index(run, item)
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "answer": right}).status_code == 200
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "answer": (right + 1) % 4}).status_code == 409

        summary = client.post("/api/video-quiz/finish", json={"run_id": run["run_id"]}).json()
        assert summary["score"] == 1  # засчитан именно первый ответ


def test_start_validates_section_and_answer_is_never_empty():
    """Несуществующий раздел и пустой ответ — понятная ошибка, а не «молча все вопросы»."""
    with _student_client() as client:
        assert client.post("/api/video-quiz/start", json={
            "section": "нет-такого", "mode": "training", "lang": "ru"}).status_code == 422
        run = _start(client, mode="testing")
        item = run["items"][0]
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"]}).status_code == 422
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "   "}).status_code == 422
        # после пустого ответа вопрос всё ещё можно отвечать
        assert client.post("/api/video-quiz/answer", json={
            "run_id": run["run_id"], "question_id": item["id"], "text": "пульсоксиметрия"}).status_code == 200


def test_voice_endpoint_does_not_crash_on_empty_transcript():
    """Пустая расшифровка не должна ронять сервер (было 500)."""
    with _student_client() as client:
        run = _start(client, section="airway")
        assert client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 8, "transcript": ""}).status_code == 422
        assert client.post("/api/video-quiz/voice", json={
            "run_id": run["run_id"], "question_id": 8, "transcript": "тридцать на два"}).status_code == 200
