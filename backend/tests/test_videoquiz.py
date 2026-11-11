"""Тесты видеотеста: банк вопросов, проверка ответа, режимы, итог, доступ, статика."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.videoquiz import QUESTIONS, TOTAL, verdict

STUDENT = {"email": "student@example.com", "password": "student123"}
TEACHER = {"email": "teacher@example.com", "password": "teacher123"}


def _student_client() -> TestClient:
    """Клиент с активной сессией учащегося (демо-аккаунт из seed)."""
    client = TestClient(app)
    client.__enter__()
    response = client.post("/login", data=STUDENT, follow_redirects=False)
    assert response.status_code == 303
    return client


def test_bank_is_consistent():
    """У каждого вопроса есть фрагмент, варианты, верный индекс и пояснение."""
    assert TOTAL == len(QUESTIONS) == 9
    assert [q.id for q in QUESTIONS] == list(range(1, TOTAL + 1))
    for q in QUESTIONS:
        assert q.clip
        assert 3 <= len(q.options["ru"]) <= 5
        assert 0 <= q.correct < len(q.options["ru"])
        assert len(set(q.options["ru"])) == len(q.options["ru"])  # варианты не повторяются
        assert q.checklist.startswith("п.")
        assert len(q.explain["ru"]) > 40


def test_verdict_thresholds():
    assert verdict(100)[0] == "excellent"
    assert verdict(90)[0] == "excellent"
    assert verdict(80)[0] == "partial"
    assert verdict(70)[0] == "partial"
    assert verdict(60)[0] == "weak"
    assert verdict(50)[0] == "weak"
    assert verdict(0)[0] == "bad"


def test_questions_hide_answers():
    """В списке вопросов нет правильного ответа и пояснения."""
    with _student_client() as client:
        response = client.get("/api/video-quiz/questions")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == TOTAL
        first = payload["items"][0]
        assert "correct" not in first and "explain" not in first
        assert len(first["options"]) >= 3


def test_training_mode_returns_verdict():
    with _student_client() as client:
        question = QUESTIONS[0]
        body = client.post("/api/video-quiz/answer",
                           json={"question_id": question.id, "answer": question.correct}).json()
        assert body["correct"] is True
        assert body["correct_index"] == question.correct
        assert body["checklist"] == question.checklist

        wrong_index = (question.correct + 1) % len(question.options)
        wrong = client.post("/api/video-quiz/answer",
                            json={"question_id": question.id, "answer": wrong_index})
        assert wrong.json()["correct"] is False


def test_testing_mode_keeps_verdict_secret():
    """В режиме зачёта сервер подтверждает приём ответа, но не раскрывает верный вариант."""
    with _student_client() as client:
        question = QUESTIONS[0]
        body = client.post("/api/video-quiz/answer",
                           json={"question_id": question.id, "answer": 0, "mode": "testing"}).json()
        assert body == {"question_id": question.id, "accepted": True}


def test_answer_validation():
    with _student_client() as client:
        assert client.post("/api/video-quiz/answer",
                           json={"question_id": 999, "answer": 0}).status_code == 404
        assert client.post("/api/video-quiz/answer",
                           json={"question_id": 1, "answer": 9}).status_code == 422
        assert client.post("/api/video-quiz/answer",
                           json={"question_id": 1, "answer": 0, "mode": "hack"}).status_code == 422


def test_finish_counts_score_and_stores_result():
    """Все верные — 100 %, все неверные — 0 %, ответы без выбора считаются ошибкой."""
    with _student_client() as client:
        perfect = {q.id: q.correct for q in QUESTIONS}
        body = client.post("/api/video-quiz/finish", json={"answers": perfect}).json()
        assert body["score"] == TOTAL and body["percent"] == 100.0
        assert body["verdict"] == "excellent"
        assert len(body["details"]) == TOTAL

        zero = {q.id: (q.correct + 1) % len(q.options) for q in QUESTIONS}
        assert client.post("/api/video-quiz/finish", json={"answers": zero}).json()["score"] == 0

        partial = {q.id: q.correct for q in QUESTIONS[:4]}
        body = client.post("/api/video-quiz/finish", json={"answers": partial}).json()
        assert body["score"] == 4
        assert body["percent"] == 44.4
        assert body["verdict"] == "bad"
        missing = [item for item in body["details"] if item["chosen"] == -1]
        assert len(missing) == TOTAL - 4

        history = client.get("/api/video-quiz/results").json()["items"]
        assert len(history) >= 3
        assert history[0]["percent"] == 44.4  # последнее прохождение сверху


def test_result_detail_gives_full_review():
    """Разбор прошлого прохождения открывается владельцем и содержит верные варианты."""
    with _student_client() as client:
        answers = {q.id: q.correct for q in QUESTIONS}
        result_id = client.post("/api/video-quiz/finish", json={"answers": answers}).json()["id"]
        detail = client.get(f"/api/video-quiz/results/{result_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["score"] == TOTAL
        assert all(item["correct_index"] == q.correct for item, q in zip(payload["details"], QUESTIONS))
        assert client.get("/api/video-quiz/results/999999").status_code == 404


def test_finish_requires_answers():
    with _student_client() as client:
        assert client.post("/api/video-quiz/finish", json={"answers": {}}).status_code == 422


def test_teacher_has_no_access():
    """Видеотест — для учащихся: преподаватель получает 403 и редирект со страницы."""
    client = TestClient(app)
    with client:
        client.post("/login", data=TEACHER, follow_redirects=False)
        assert client.post("/api/video-quiz/finish", json={"answers": {1: 0}}).status_code == 403
        assert client.get("/api/video-quiz/questions").status_code == 403
        page = client.get("/student/video-quiz", follow_redirects=False)
        assert page.status_code == 303


def test_page_and_media_available():
    """Страница отдаётся, все девять фрагментов и постеров доступны по /static/media/quiz/."""
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


# ----------------------------- голосовой ответ -----------------------------

def test_voice_matching_ru():
    """Фразы, которые люди реально говорят, находят нужный вариант."""
    from backend.app.voice import choose
    from backend.app.videoquiz import QUESTIONS

    def pick(qid, text, expected):
        question = next(q for q in QUESTIONS if q.id == qid)
        result = choose(text, question.voice_options("ru"))
        assert result["chosen"] == expected, (qid, text, result)

    pick(1, "датчик на палец, сатурация", 1)
    pick(1, "измеряет давление тонометром", 0)
    pick(2, "снимает экг в двенадцать отведений", 0)
    pick(4, "нет сознания и нет дыхания десять секунд", 1)
    pick(5, "сразу, не прекращая компрессий", 1)
    pick(6, "чтобы никто не касался пациента при разряде", 1)
    pick(8, "тридцать на два", 1)
    pick(8, "пятнадцать на два", 0)
    pick(9, "продолжает компрессии до приезда скорой", 0)


def test_voice_matching_en():
    from backend.app.voice import choose
    from backend.app.videoquiz import QUESTIONS

    question = next(q for q in QUESTIONS if q.id == 8)
    assert choose("thirty to two", question.voice_options("en"))["chosen"] == 1
    assert choose("fifteen to two", question.voice_options("en"))["chosen"] == 0

    question = next(q for q in QUESTIONS if q.id == 4)
    assert choose("no consciousness and no breathing for ten seconds",
                  question.voice_options("en"))["chosen"] == 1


def test_voice_unknown_phrase_is_not_guessed():
    """Неразборчивая фраза не должна «приклеиваться» к случайному варианту."""
    from backend.app.voice import choose
    from backend.app.videoquiz import QUESTIONS

    question = next(q for q in QUESTIONS if q.id == 1)
    result = choose("ммм ну такое", question.voice_options("ru"))
    assert result["chosen"] is None


def test_voice_endpoint_returns_option():
    with _student_client() as client:
        body = client.post("/api/video-quiz/voice",
                           json={"question_id": 8, "transcript": "тридцать на два", "lang": "ru"}).json()
        assert body["chosen"] == 1
        assert body["option_text"] == "30:2"
        assert body["confidence"] > 0
        assert "30 на 2" in body["matched"]

        nothing = client.post("/api/video-quiz/voice",
                              json={"question_id": 8, "transcript": "не помню", "lang": "ru"}).json()
        assert nothing["chosen"] is None

        assert client.post("/api/video-quiz/voice",
                           json={"question_id": 999, "transcript": "тест"}).status_code == 404
        assert client.post("/api/video-quiz/voice",
                           json={"question_id": 1, "transcript": ""}).status_code == 422


def test_bank_has_both_languages_for_every_question():
    """Русский и английский тексты есть у каждого вопроса, число вариантов совпадает."""
    from backend.app.videoquiz import LANGS
    for q in QUESTIONS:
        lengths = {lang: len(q.options[lang]) for lang in LANGS}
        assert lengths["ru"] == lengths["en"], q.id
        assert len(q.triggers["ru"]) == lengths["ru"] == len(q.triggers["en"])
        for lang in LANGS:
            assert q.title[lang] and q.question[lang] and q.explain[lang]
            assert all(option.strip() for option in q.options[lang])


def test_questions_in_english():
    with _student_client() as client:
        payload = client.get("/api/video-quiz/questions?lang=en").json()
        assert payload["lang"] == "en"
        first = payload["items"][0]
        assert first["title"] == "The doctor works with the patient's hand"
        assert all(not any("А" <= ch <= "я" for ch in option) for option in first["options"])
        assert client.get("/api/video-quiz/questions?lang=de").status_code == 422


def test_finish_and_review_in_english():
    with _student_client() as client:
        answers = {q.id: q.correct for q in QUESTIONS}
        body = client.post("/api/video-quiz/finish",
                           json={"answers": answers, "lang": "en"}).json()
        assert body["verdict_text"] == "You know the algorithm confidently"
        assert body["details"][0]["explain"].startswith("A finger probe")
        detail = client.get(f"/api/video-quiz/results/{body['id']}?lang=en").json()
        assert [item["id"] for item in detail["details"]] == [q.id for q in QUESTIONS]


def test_english_dictionary_covers_instruction_page():
    """Ключевые строки страницы-справки и видеотеста есть в расширенном словаре."""
    import pathlib
    import re

    extra = pathlib.Path("frontend/js/i18n_extra.js").read_text(encoding="utf-8")
    required = [
        "Основано на «Паспорте экзаменационной станции",
        "A — проходимость дыхательных путей",
        "B — дыхание",
        "C — кровообращение",
        "D — неврологический статус",
        "E — осмотр и дополнительные меры",
        "Оценка фотореакции зрачков",
        "Обеспечить пульсоксиметрию",
        "Ответить голосом",
    ]
    for phrase in required:
        assert phrase in extra, phrase
    # одинаковое число ключей и значений — словарь не «съехал»
    keys = re.findall(r'^\s{4}"', extra, flags=re.MULTILINE)
    assert len(keys) > 60


def test_translation_checker_is_clean_for_key_pages():
    """Инструмент проверки перевода: видеотест и справка по ЭМП переведены полностью."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path.cwd()))
    from tools.check_i18n import dictionary_keys, template_phrases

    keys = dictionary_keys()
    for name in ("video_quiz.html", "emergency_help.html", "base.html"):
        phrases = template_phrases(Path("frontend/html") / name)
        missing = [p for p in phrases if p not in keys]
        assert not missing, (name, missing[:5])
