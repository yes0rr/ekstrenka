"""Проверка свободного ответа «по смыслу», а не по буквам.

Задача: учащийся пишет или говорит ответ словами, и формулировка почти никогда
не совпадает с эталоном дословно («давление низкое» вместо «САД 80–90, гипотония»).
Нужно понять, что ответ верный по сути.

Как считаем (без внешних сервисов, на процессоре сервера):

  1. Приводим текст к нормальному виду: нижний регистр, ё→е, убираем пунктуацию,
     числа оставляем и дополнительно пишем словами («30» → «тридцать»).
  2. Приводим слова к основе. Если установлен pymorphy3 — настоящая лемматизация
     (лучше), иначе простая обрезка окончаний (работает и без словаря).
  3. У вопроса есть «ключевые группы» — набор синонимов на каждый смысловой кусок
     эталона. Группа закрыта, если в ответе встретилось хотя бы одно слово из неё.
     Доля закрытых групп = покрытие.
     Дополнительно считаем покрытие слов эталона (сколько значимых слов эталона
     учащийся упомянул) — это спасает, когда ответ пересказан своими словами.
  4. Итог = максимум из двух покрытий.
        ≥ 0,75 — верно;
        0,50–0,75 — принято, но неполно (засчитываем, помечаем «не всё сказано»);
        < 0,50 — неверно; если ответ совсем короткий и ничего не совпало —
        «не расслышал/не понял, повторите» (не считаем ошибкой).
  5. Если в ответе есть слова из must_not («не показана» там, где показана), ответ
     сразу неверный — отрицание важнее совпадений.

Задел на нейросеть (необязательный шаг). Если понадобится понимать совсем вольный
пересказ, включается флаг SEMANTIC_EMBEDDINGS=1: тогда ответ и эталон переводятся
в векторы маленькой моделью rubert-tiny2 в формате ONNX (~30 МБ, ставится рядом с
Whisper, работает на CPU через onnxruntime, без torch) и сравниваются по косинусу.
Место подключения — функция semantic_similarity() ниже: пока она возвращает None,
и решение принимается правилами. Ничего другого менять не нужно.
"""
from __future__ import annotations

import math
import os
import re
from functools import lru_cache

_ONES = ("ноль один два три четыре пять шесть семь восемь девять десять "
         "одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать "
         "семнадцать восемнадцать девятнадцать").split()
_TENS = "_ _ двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто".split()
_HUNDREDS = "_ сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот".split()

# слова-числительные не трогаем основой: «восемь» не должно стать «восем»
_NUM_WORDS = set(_ONES) | set(_TENS) | set(_HUNDREDS) | {"ноль"}

_WORD_RE = re.compile(r"[а-яa-z0-9]+(?:[.,][0-9]+)?", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\wа-яё\s.,%-]+", re.IGNORECASE)

# окончания, которые срезаем, если pymorphy3 не установлен
_ENDINGS = ("ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими", "ая", "яя", "ое",
            "ее", "ые", "ие", "ой", "ей", "ый", "ий", "ов", "ев", "ах", "ях", "ом",
            "ем", "ую", "юю", "ам", "ям", "а", "я", "о", "е", "ы", "и", "у", "ю", "ь")


@lru_cache(maxsize=1)
def _morph():
    """pymorphy3, если он есть в окружении (ставится вместе с requirements-voice)."""
    try:
        import pymorphy3  # type: ignore

        return pymorphy3.MorphAnalyzer()
    except Exception:  # нет пакета — работаем обрезкой окончаний
        return None


def _number_words(token: str) -> list[str]:
    """«30» → ['тридцать'], «0,9» → ['ноль', 'девять'], «88» → ['восемьдесят', 'восемь']."""
    if not token or not token[0].isdigit():
        return []
    out: list[str] = []
    for part in re.split(r"[.,]", token):
        if not part.isdigit():
            continue
        value = int(part)
        if value < 20:
            out.append(_ONES[value])
        elif value < 100:
            tens, ones = divmod(value, 10)
            out.append(_TENS[tens])
            if ones:
                out.append(_ONES[ones])
        else:
            hundreds, rest = divmod(value, 100)
            if 0 < hundreds <= 9:
                out.append(_HUNDREDS[hundreds])
            if rest:
                out.extend(_number_words(str(rest)))
    return out


def _stem(word: str) -> str:
    morph = _morph()
    if morph is not None:
        try:
            return morph.parse(word)[0].normal_form
        except Exception:
            pass
    for ending in _ENDINGS:
        if len(word) - len(ending) >= 4 and word.endswith(ending):
            return word[: len(word) - len(ending)]
    return word


def tokens(text: str) -> list[str]:
    """Слова текста в нормальной форме (+ числа, записанные словами)."""
    text = (text or "").lower().replace("ё", "е")
    text = _PUNCT_RE.sub(" ", text)
    result: list[str] = []
    for raw in _WORD_RE.findall(text):
        raw = raw.strip(".,")
        if not raw:
            continue
        if raw[0].isdigit():
            result.append(raw)
            result.extend(_number_words(raw))
            continue
        if raw in _NUM_WORDS:     # числительное словом — оставляем как есть
            result.append(raw)
            continue
        result.append(_stem(raw))
    return result


def _norm_phrase(phrase: str) -> list[str]:
    return tokens(phrase)


def _distance(a: str, b: str) -> int:
    """Расстояние Левенштейна — для коротких слов («нужн» и «нужен» отличаются на 1)."""
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _same_word(a: str, b: str) -> bool:
    """Одно и то же слово в разных формах: совпадает почти весь общий префикс.

    «нужен» и «нужна», «давление» и «давления» — да.
    «проводим» и «прослушивается» — нет (общий только «про»).
    """
    if a == b:
        return True
    if a[0].isdigit() or b[0].isdigit():
        return False
    shorter = min(len(a), len(b))
    if shorter <= 4:                      # короткие слова: допустима одна опечатка/форма
        return _distance(a, b) <= 1
    common = 0
    for left, right in zip(a, b):
        if left != right:
            break
        common += 1
    return common >= max(4, shorter - 1)


def _letter_hit(word: str, haystack: set[str]) -> bool:
    if word in haystack:
        return True
    return any(_same_word(word, other) for other in haystack)


def _contains(needle: list[str], haystack: set[str], haystack_text: str) -> bool:
    """Фраза-синоним встречается в ответе: по словам (с учётом форм) или числом."""
    if not needle:
        return False
    digits = [w for w in needle if w[0].isdigit()]
    if digits:
        # «88» в ответе может быть написано словами: «восемьдесят восемь»
        for value in digits:
            spoken = _number_words(value)
            if value in haystack or (spoken and all(w in haystack for w in spoken)):
                continue
            return False
        rest = [w for w in needle if not w[0].isdigit()]
        return all(_letter_hit(w, haystack) for w in rest)
    if len(needle) == 1:
        return _letter_hit(needle[0], haystack)
    if " ".join(needle) in haystack_text:
        return True
    # фраза из нескольких слов: все слова должны найтись рядом (в том же порядке)
    words = haystack_text.split()
    for start in range(len(words)):
        for shift in range(len(needle)):
            index = start + shift
            if index >= len(words) or not _same_word(needle[shift], words[index]):
                break
        else:
            return True
    return False


_UNITS = {"мг", "мл", "ед", "вв", "вм", "проц", "сек", "мин", "мм", "рт", "ст", "кг", "час"}


def _is_content(synonym: str) -> bool:
    """Смысловое слово, а не единица измерения: «аспирин» — да, «мг» — нет."""
    word = synonym.strip().lower()
    if not word.isalnum() or word.isdigit():
        return False
    # аббревиатуры из чек-листа (ЧДД, ЧСС, ЭКГ, АД) — тоже смысловые слова
    return word not in _UNITS and len(word) >= 2


def _group_hit(group: tuple[str, ...], haystack: set[str], haystack_text: str) -> float:
    """Совпала ли группа-синоним: 1.0 — по слову, 0.5 — только по числу, 0 — нет.

    Число без слова («80» в ответе про давление) — слабое доказательство смысла,
    поэтому одна цифра сама по себе группу не закрывает.
    """
    best = 0.0
    for synonym in group:
        if not _contains(_norm_phrase(synonym), haystack, haystack_text):
            continue
        best = max(best, 1.0 if _is_content(synonym) else 0.5)
        if best == 1.0:
            break
    return best


def _significance(word: str) -> bool:
    """Значимые слова эталона: не предлоги и не короче 4 букв."""
    return len(word) >= 4 and word not in {"если", "также", "после", "через", "этом", "который"}


def match(question, answer: str) -> dict:
    """Сравнить свободный ответ с эталоном вопроса.

    Возвращает словарь:
      verdict  — correct | partial | wrong | retry
      coverage — 0…1, насколько ответ закрывает эталон
      matched  — какие смысловые куски распознаны (для подсказки учащемуся)
      missed   — чего не хватило
      reference— эталон, который показываем после ответа
    """
    raw = (answer or "").strip()
    haystack_text = " ".join(tokens(raw))
    haystack = set(haystack_text.split())

    blocked = [phrase for phrase in getattr(question, "must_not", ())
               if _contains(_norm_phrase(phrase), haystack, haystack_text)]
    if blocked:
        return {"verdict": "wrong", "coverage": 0.0,
                "matched": [], "missed": ["отрицание меняет смысл ответа"],
                "reference": question.reference["ru"] if hasattr(question, "reference") else "",
                "blocked": blocked}

    groups = getattr(question, "keys", ()) or ()
    hit, miss, group_score = [], [], 0.0
    scores: list[float] = []
    content_hit = False
    for group in groups:
        score = _group_hit(group, haystack, haystack_text)
        scores.append(score)
        group_score += score
        if score >= 1.0:
            content_hit = True
        (hit if score > 0 else miss).append(group[0])
    key_cover = group_score / len(groups) if groups else 0.0
    # первая группа — главная мысль ответа; без неё ответ не считаем верным,
    # иначе «морфин в вену» засчитывался бы как ответ про аспирин
    main_hit = bool(scores) and scores[0] >= 1.0

    reference_words = {w for w in tokens(getattr(question, "reference", {}).get("ru", ""))
                       if _significance(w)}
    ref_hits = sum(1 for w in reference_words if _letter_hit(w, haystack))
    ref_cover = (ref_hits / len(reference_words)) if reference_words else 0.0

    # ключевые группы весят больше: они и есть «суть» ответа
    coverage = round(0.7 * key_cover + 0.3 * ref_cover, 3)

    # модель понимает пересказ своими словами: если векторная близость высокая,
    # ответ не может быть «неверным» — максимум «принято, но сказано не всё»
    semantic = semantic_similarity(raw, getattr(question, "reference", {}).get("ru", ""))
    if semantic is not None:
        coverage = max(coverage, round(semantic * 0.95, 3))

    if len(haystack) <= 1 and not hit:
        verdict = "retry"
    elif key_cover >= 0.75 and main_hit:
        verdict = "correct"
    elif key_cover >= 0.33 and content_hit:
        verdict = "partial"
    elif content_hit and coverage >= 0.8:   # пересказ своими словами, близкий к эталону
        verdict = "partial"
    elif semantic is not None and semantic >= 0.72:   # понял смысл, но слов эталона почти нет
        verdict = "partial"
    else:
        verdict = "wrong"

    return {
        "verdict": verdict,
        "coverage": round(coverage, 2),
        "matched": hit[:6],
        "missed": [] if verdict == "correct" else miss[:6],
        "reference": getattr(question, "reference", {}).get("ru", ""),
    }


def semantic_similarity(answer: str, reference: str) -> float | None:
    """Векторное сравнение ответа и эталона — задел на маленькую модель.

    Пока возвращает None: правилами уже закрывается обычный пересказ.
    Включается флагом SEMANTIC_EMBEDDINGS=1 (см. tools/download_semantic_model.py).
    Модель: rubert-tiny2 в ONNX, косинус между усреднёнными векторами слов.
    """
    if os.getenv("SEMANTIC_EMBEDDINGS", "0") != "1":
        return None
    try:  # pragma: no cover - зависит от установленной модели
        from .semantic_onnx import similarity

        return similarity(answer, reference)
    except Exception:
        return None


def char_similarity(a: str, b: str) -> float:
    """Косинус по триграммам — простой запасной вариант, если ничего другого нет."""
    def grams(text: str) -> dict[str, int]:
        text = " ".join(tokens(text))
        out: dict[str, int] = {}
        for i in range(len(text) - 2):
            out[text[i:i + 3]] = out.get(text[i:i + 3], 0) + 1
        return out

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    common = set(ga) & set(gb)
    dot = sum(ga[g] * gb[g] for g in common)
    na = math.sqrt(sum(v * v for v in ga.values()))
    nb = math.sqrt(sum(v * v for v in gb.values()))
    return round(dot / (na * nb), 3)
