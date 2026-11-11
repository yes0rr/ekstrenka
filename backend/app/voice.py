"""Голосовой ответ в видеотесте: сопоставление фразы с вариантами ответа.

Распознавание речи делает браузер (Web Speech API, в Chrome/Edge — нейросеть Google,
бесплатно и без нагрузки на наш сервер). Сюда приходит уже текстовая расшифровка,
а сервер решает, какому варианту она соответствует: правильные ответы по-прежнему
не уходят в браузер.

Сопоставление простое и предсказуемое: у каждого варианта есть список слов-подсказок
(синонимы, числа словами), фраза нормализуется и сравнивается по вхождению.
Никакой модели внутри нет — поэтому результат объясним: видно, какие слова совпали.
"""
from __future__ import annotations

import re

# числа словами → цифры: «тридцать на два» и «30 на 2» должны совпасть
NUMBER_WORDS = {
    "ноль": "0", "один": "1", "одно": "1", "одна": "1", "два": "2", "две": "2",
    "три": "3", "четыре": "4", "пять": "5", "шесть": "6", "семь": "7",
    "восемь": "8", "девять": "9", "десять": "10", "одиннадцать": "11",
    "двенадцать": "12", "пятнадцать": "15", "двадцать": "20", "тридцать": "30",
    "пятьдесят": "50", "шестьдесят": "60", "сто": "100",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "fifty": "50", "sixty": "60", "hundred": "100",
}

_EDGE = re.compile(r"(?<![0-9a-zа-я]){}(?![0-9a-zа-я])")


def normalize(text: str) -> str:
    """Нижний регистр, ё→е, без пунктуации, числа словами → цифрами."""
    raw = (text or "").lower().replace("ё", "е")
    raw = re.sub(r"[^0-9a-zа-я]+", " ", raw)
    words = [NUMBER_WORDS.get(word, word) for word in raw.split()]
    return " ".join(words).strip()


def _contains(haystack: str, needle: str) -> bool:
    """Вхождение по границам слов: «экг» находится в «экг в 12 отведениях», но не в «экране»."""
    return re.search(_EDGE.pattern.format(re.escape(needle)), haystack) is not None


def score_option(transcript: str, triggers: tuple[str, ...]) -> tuple[float, list[str]]:
    """Сколько подсказок варианта прозвучало. Возвращает (вес, найденные подсказки)."""
    text = normalize(transcript)
    if not text:
        return 0.0, []
    weight = 0.0
    matched: list[str] = []
    for trigger in triggers:
        needle = normalize(trigger)
        if not needle or not _contains(text, needle):
            continue
        matched.append(trigger)
        # длинная подсказка весит больше: «вызов скорой» ценнее, чем «и»
        weight += 1.0 + 0.25 * len(needle.split())
    return weight, matched


def choose(transcript: str, options: tuple[tuple[str, ...], ...],
           min_weight: float = 1.0) -> dict:
    """Выбрать вариант ответа по фразе.

    options — подсказки каждого варианта (в том же порядке, что и варианты ответа).
    Возвращает номер варианта (или None), уверенность 0…1 и совпавшие слова.
    """
    scored = [score_option(transcript, triggers) for triggers in options]
    found = [(index, weight, matched) for index, (weight, matched) in enumerate(scored) if weight > 0]
    if not found:
        return {"chosen": None, "confidence": 0.0, "matched": [], "transcript": transcript}

    found.sort(key=lambda item: item[1], reverse=True)
    best_index, best_weight, best_matched = found[0]
    total = sum(weight for _, weight, _ in found)
    confidence = round(best_weight / total, 2) if total else 0.0

    # один вариант заметно лучше остальных и есть минимальный вес совпадений
    if best_weight < min_weight or (len(found) > 1 and best_weight - found[1][1] < 0.5):
        return {"chosen": None, "confidence": confidence, "matched": best_matched,
                "transcript": transcript, "ambiguous": True}

    return {"chosen": best_index, "confidence": confidence, "matched": best_matched,
            "transcript": transcript}
