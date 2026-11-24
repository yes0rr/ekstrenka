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

# короткие, но осмысленные: путь введения, номер межреберья, сторона
_SHORT_CONTENT = {"в/м", "в/в", "п/к", "ii", "2", "3", "80", "40"}
# сокращения путей введения: дроби «в/м» токенайзер рвёт на «в» и «м», поэтому ищем подстрокой
_ROUTE_RE = re.compile(r"в\s*/\s*([вмк])")
# как студент может сказать путь введения обычными словами
_ROUTE_WORDS = {
    "в/м": ("мышц", "мышцу", "внутримышечн", "бедро", "бедра", "плечо"),
    "в/в": ("вену", "вены", "внутривенн", "капельниц"),
    "п/к": ("подкожн", "под кожу"),
}


def _is_dose(word: str) -> bool:
    """«0,5», «2,5», «80», «1000» — дозировка/объём. Пишется цифрами или словами."""
    word = word.strip().lower()
    if not word:
        return False
    if word[0].isdigit():
        return True
    return word in _NUM_WORDS


def _is_content(synonym: str) -> bool:
    """Смысловое слово, а не единица измерения: «аспирин» — да, «мг» — нет.

    Дозировка с дробной частью («0,5», «2,5») — значимая: это доза препарата.
    """
    word = synonym.strip().lower().replace(".", ",")
    if _is_dose(word):        # 0,5 / 2,5 / 80 — дозировки, они важны
        return True
    if not word.isalnum() or word.isdigit():
        return False
    # аббревиатуры из чек-листа (ЧДД, ЧСС, ЭКГ, АД) — тоже смысловые слова
    if word in _SHORT_CONTENT:
        return True
    if word in {"ii", "iii", "iv"}:          # римские цифры — номер межреберья
        return True
    return word not in _UNITS and len(word) >= 2


def _route_hit(synonym: str, haystack_text: str) -> bool:
    """«в/м» в ответе: токенайзер рубит дробь, поэтому проверяем по тексту."""
    plain = synonym.strip().lower()
    text = f" {haystack_text} "
    if plain in _ROUTE_WORDS and any(f" {w} " in text for w in _ROUTE_WORDS[plain]):
        return True
    match_route = _ROUTE_RE.fullmatch(plain.replace(" ", ""))
    if not match_route:
        return False
    letter = match_route.group(1)
    # «в/в» после токенизации превращается в «в в» — учитываем и это
    variants = {f" в {letter}", f"в/{letter}", f" в {letter} "}
    if letter in {"в", "м", "к"}:
        variants.add(f"в {letter}")
    return any(v in f" {haystack_text} " for v in variants)


# ---------------------------- проверка доз и объёмов ----------------------------
# Преподаватель ставит дозу как есть: «0,5 мг», «1000–2000 мл», «40–80 мг», «70–100 Ед/кг».
# Нам нужно понять не «есть ли цифра», а «верное ли число и в тех ли единицах».
_VALUE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:[-–—]\s*(\d+(?:[.,]\d+)?))?\s*([а-яa-z%]*)",
                       re.IGNORECASE)
_UNIT_ALIASES = {
    "мг": "мг", "миллиграмм": "мг", "миллиграмма": "мг", "миллиграммов": "мг",
    "мкг": "мкг", "микрограмм": "мкг", "микрограмма": "мкг",
    "г": "г", "грамм": "г", "грамма": "г", "граммов": "г",
    "мл": "мл", "миллилитр": "мл", "миллилитра": "мл", "миллилитров": "мл",
    "л": "л", "литр": "л", "литра": "л",
    "ед": "ед", "единиц": "ед", "единицы": "ед", "единица": "ед",
    "%": "%",
    "кг": "кг", "килограмм": "кг",
    "мм": "мм",
}
# допуск: дозу можно назвать чуть иначе, но не «9999 мг»
_TOLERANCE = {"мг": 0.1, "мкг": 0.1, "г": 0.1, "мл": 0.1, "л": 0.1, "ед": 0.1, "кг": 0.1, "%": 1.0, "": 0.1}


def _to_float(text: str) -> float | None:
    try:
        return float(str(text).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _unit_of(word: str) -> str:
    word = (word or "").strip().lower().replace(".", "").replace("/", "")
    if not word:
        return ""
    if word in _UNIT_ALIASES:
        return _UNIT_ALIASES[word]
    for ending in ("ами", "ах", "ов", "а", "ы", "и"):
        if word.endswith(ending) and word[: -len(ending)] in _UNIT_ALIASES:
            return _UNIT_ALIASES[word[: -len(ending)]]
    # «мг/кг», «ед/кг», «мг/мл» — единица на массу: берём первую часть
    head = word.split("/")[0]
    return _UNIT_ALIASES.get(head, "")


def parse_values(text: str) -> list[tuple[float | None, float | None, str, str]]:
    """«эпинефрин 0,5 мг; 1000–2000 мл» → [(0.5, None, 'мг', 'эпинефрин'), (1000, 2000, 'мл', '')].

    Последний элемент — слово перед числом: по нему видно, к какому препарату
    относится доза. Работаем по «сырому» тексту, потому что токенизатор вставляет
    между числом и единицей слова-числительные («0,5» → «ноль», «пять»).
    """
    raw = (text or "").lower().replace("ё", "е")
    out: list[tuple[float | None, float | None, str, str]] = []
    for found in _VALUE_RE.finditer(raw):
        low = _to_float(found.group(1))
        high = _to_float(found.group(2)) if found.group(2) else None
        unit = _unit_of(found.group(3) or "")
        if not unit:                       # «1000 мг» / «1000 (мл)» — единица следующим словом
            rest = raw[found.end(): found.end() + 12].strip(" )(,.;")
            word = re.split(r"[\s,;)(]+", rest, maxsplit=1)[0] if rest else ""
            unit = _unit_of(word)
        anchor = ""
        before = re.findall(r"[а-яa-z0-9]+", raw[: found.start()])
        for word in reversed(before[-4:]):
            if word[0].isdigit() or _unit_of(word):
                continue
            anchor = word
            break
        out.append((low, high, unit, anchor))
    return out


def _value_ok(expected: tuple[float | None, float | None, str], found) -> bool:
    """Подходит ли найденное число под ожидаемую дозу: те же единицы, значение в допуске."""
    low, high, unit = expected
    if low is None:
        return False
    found_low, found_high, found_unit, _anchor = found
    tolerance = _TOLERANCE.get(unit, 0.1)
    top = high if high is not None else low
    bottom = low
    # единицы должны совпадать: «9999 мг» не закроет «1000–2000 мл»,
    # «0,5 мг» не закроет «0,5 %». Если единица не распознана — сравниваем только число.
    if unit and found_unit and unit != found_unit:
        return False
    for value in (found_low, found_high):
        if value is None:
            continue
        if unit == "%":            # «1191 %» не должно пройти как «0,9 %»
            if abs(value - bottom) <= 0.05:
                return True
            continue
        if bottom - tolerance <= value <= top + tolerance:
            return True
    return False


def _expected_lines(text: str) -> list[str]:
    """Данные критерия или эталон → строки требований: «эпинефрин ... ; инфузия ...»."""
    parts = re.split(r"[;\n]", text or "")
    return [part.strip(" .") for part in parts if parse_values(part)]


def _dose_review(expected_text: str, answer_raw: str) -> tuple[bool, list[dict]]:
    """Сверка чисел ответа с эталоном: верные ли дозы, объёмы и проценты.

    Каждая строка эталона (препарат + его доза) — отдельное требование.
    Строка закрыта, если в ответе есть хотя бы одно её число с теми же единицами
    (для промежутка «1000–2000 мл» подходит любое значение внутри).
    Возвращает «всё верно» и ошибки вида {said: «9999 мг», expected: «эпинефрин ... 0,5 мг»}.
    """
    found = parse_values(answer_raw)
    if not found:
        return True, []                     # чисел нет — оценивать дозы не по чему
    ok_all = True
    mistakes: list[dict] = []
    for line in _expected_lines(expected_text):
        expected = [(low, high, unit) for low, high, unit, _anchor in parse_values(line) if low is not None]
        if not expected:
            continue
        if any(_value_ok(exp, item) for exp in expected for item in found):
            continue
        ok_all = False
        units = {exp[2] for exp in expected if exp[2]}
        said = next((item for item in found if item[2] in units), None)
        mistakes.append({"said": _format_value(said) if said else "",
                         "expected": line[:120]})
    return ok_all, mistakes


def _format_value(value) -> str:
    """(1000.0, 2000.0, 'мл', ...) → «1000–2000 мл»."""
    low, high, unit = value[0], value[1], value[2]
    if low is None:
        return ""
    def num(x: float) -> str:
        return str(int(x)) if float(x).is_integer() else str(round(x, 2)).replace(".", ",")
    text = num(low) if high is None else f"{num(low)}–{num(high)}"
    return f"{text} {unit}".strip()


def _dose_groups(groups) -> list[tuple[str, ...]]:
    """Группы, где перечислены только дозы/единицы («0,5», «1000», «2000», «мл»)."""
    out = []
    for group in groups or ():
        if not group:
            continue
        if any(_is_dose(synonym) for synonym in group) and all(
                _is_dose(synonym) or _unit_of(synonym) or synonym.strip().lower() in _UNITS
                for synonym in group):
            out.append(tuple(group))
    return out


def _flat_groups(groups) -> tuple[tuple[str, ...], ...]:
    """((a, b), (c, d)) → (a, b), (c, d); ((«в/м», «бедр»), ...) тоже раскрывается."""
    out: list[tuple[str, ...]] = []
    for group in groups or ():
        if group and isinstance(group[0], tuple):
            out.extend(tuple(str(x) for x in item) for item in group)
        else:
            out.append(tuple(str(x) for x in group))
    return tuple(out)


def _group_hit(group: tuple[str, ...], haystack: set[str], haystack_text: str,
               raw_text: str | None = None) -> float:
    """Совпала ли группа-синоним: 1.0 — по слову, 0.5 — только по числу, 0 — нет.

    Число без слова («80» в ответе про давление) — слабое доказательство смысла,
    поэтому одна цифра сама по себе группу не закрывает.
    """
    # дозная группа («0,5 мг», «1000–2000 мл»): мало найти цифру — она должна быть верной
    expected = [(low, high, unit) for low, high, unit, _anchor in parse_values(" ".join(group))
                if low is not None]
    if expected and all(_is_dose(synonym) or _unit_of(synonym) or synonym.strip().lower() in _UNITS
                        for synonym in group):
        found = parse_values(raw_text or haystack_text)
        return 1.0 if any(_value_ok(exp, item) for exp in expected for item in found) else 0.0

    best = 0.0
    for synonym in group:
        if _route_hit(synonym, haystack_text):      # в/м, в/в, п/к
            return 1.0
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
        score = _group_hit(group, haystack, haystack_text, raw)
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

    # ---- вопросы преподавателя: один вопрос — один большой ответ, оценка по критериям ----
    # Каждый критерий закрыт полностью (все его группы слов найдены) или частично.
    # Балл = доля закрытых критериев: 5 из 5 — верно, 3 из 5 — половина, 1 из 5 — мало.
    criteria = tuple(getattr(question, "criteria", ()) or ())
    if criteria:
        # критерии из файла преподавателя бывают двух видов:
        #   у критерия свои данные (список препаратов в столбце «правильные данные»);
        #   у критерия данных нет — значит, оценивается столбец выше
        #   (например, «приоритетность» — препараты жёлтого столбца).
        by_criterion = [[] for _ in criteria]
        pending = []
        for index, (_name, _data, groups_c) in enumerate(criteria):
            flat = list(_flat_groups(groups_c))
            if flat:
                by_criterion[index].extend(flat)
                pending = flat
            elif index > 0:
                by_criterion[index - 1].extend(pending)
        if not any(by_criterion):                 # страховка: раскладываем как есть
            by_criterion = [list(_flat_groups(c[2])) for c in criteria]

        detail = []
        for (name, data, _groups), flat in zip(criteria, by_criterion):
            # критерий «про дозы» — тот, у которого ВСЕ ключевые группы — дозные
            # («0,5», «1000», «2000», «мл», …). Тогда считаем по строкам данных,
            # а не по ключевым словам: важно не «есть ли цифра», а верное ли число.
            dose_only = bool(flat) and len(_dose_groups(flat)) == len(flat)
            lines = _expected_lines(data) if (dose_only or not flat) else []
            if lines:
                # критерий про дозы: смотрим не «есть ли цифра», а «верное ли значение
                # и в тех ли единицах». Каждая строка данных — отдельное требование.
                found = parse_values(raw)
                closed_lines, hit_values, mistakes, used = 0, [], [], set()
                for line in lines:
                    expected = [(low, high, unit) for low, high, unit, _a in parse_values(line)
                                if low is not None]
                    good = next((item for item in found
                                 if any(_value_ok(exp, item) for exp in expected)), None)
                    if good is not None:
                        closed_lines += 1
                        hit_values.append(_format_value(good))
                        used.add(good)
                        continue
                    units = {exp[2] for exp in expected if exp[2]}
                    # показываем, что учащийся сказал вместо нужной дозы (то же измерение),
                    # но только если это число не засчитано другой строкой
                    said = next((item for item in found
                                 if item[2] in units and item not in used), None)
                    mistakes.append({"said": _format_value(said) if said else "",
                                     "expected": line[:120]})
                part = closed_lines / len(lines)
                detail.append({"criterion": name, "marks": data,
                               "done": part >= 0.999, "part": round(part, 2),
                               "hit": hit_values, "of": len(lines), "wrong": mistakes})
                continue

            if not flat:
                detail.append({"criterion": name, "marks": data, "done": False,
                               "part": 0.0, "hit": [], "of": 0, "wrong": []})
                continue
            scores_c = [_group_hit(g, haystack, haystack_text, raw) for g in flat]
            part = sum(scores_c) / len(scores_c)
            detail.append({"criterion": name, "marks": data,
                           "done": part >= 0.999, "part": round(part, 2),
                           "hit": [g[0] for g, sc in zip(flat, scores_c) if sc >= 0.5],
                           "of": len(flat), "wrong": []})
        closed = sum(1 for d in detail if d["done"])
        share = round(sum(d["part"] for d in detail) / len(detail), 3)
        if share >= 0.999:
            verdict = "correct"
        elif share > 0.2:
            verdict = "partial"
        else:
            verdict = "wrong"

        return {
            "verdict": verdict,
            "coverage": share,
            "score": round(share, 3),          # прогресс по критериям: 0…1
            "closed": closed,                  # сколько критериев закрыто полностью
            "total": len(detail),
            "criteria": detail,
            "doses": [m for d in detail for m in d.get("wrong", [])],
            "matched": [d["criterion"] for d in detail if d["done"]],
            "missed": [d["criterion"] for d in detail if not d["done"]],
            "reference": getattr(question, "reference", {}).get("ru", ""),
        }

    # вопрос про дозы/объёмы: препараты без цифр — не полный ответ.
    # считаем только группы, где ВСЕ синонимы — числа/единицы («мг», «мл», «150», «300»),
    # иначе группа ('ii','2','второ') ложно считалась бы дозировкой
    def _is_dose_group(group) -> bool:
        return bool(group) and all(_is_dose(x) or x.strip().lower() in _UNITS for x in group)

    dose_groups = [g for g in groups if _is_dose_group(g)]
    doses_named = bool(dose_groups) and any(
        _group_hit(g, haystack, haystack_text, raw) >= 1.0 for g in dose_groups)

    if len(haystack) <= 1 and not hit:
        verdict = "retry"
    elif key_cover >= 0.75 and main_hit and (not dose_groups or doses_named):
        verdict = "correct"
    elif key_cover >= 0.33 and content_hit:
        verdict = "partial"
    elif content_hit and coverage >= 0.8:   # пересказ своими словами, близкий к эталону
        verdict = "partial"
    elif semantic is not None and semantic >= 0.72:   # понял смысл, но слов эталона почти нет
        verdict = "partial"
    else:
        verdict = "wrong"

    # если в ответе названы дозы, но с неверными числами/единицами — «верно» не ставим
    doses_ok, doses = _dose_review(getattr(question, "reference", {}).get("ru", ""), raw)
    if not doses_ok and verdict == "correct":
        verdict = "partial"
    return {
        "verdict": verdict,
        "coverage": round(coverage, 2),
        "doses": doses,
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
