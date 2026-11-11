"""Проверка перевода: какие русские фразы в шаблонах не попадут в английскую версию.

Запуск из папки ispytaniya:
    python tools/check_i18n.py                # сводка по всем шаблонам
    python tools/check_i18n.py video_quiz      # только один шаблон, со списком фраз

Скрипт ничего не меняет: он читает frontend/html/*.html и словари frontend/js/i18n.js,
frontend/js/i18n_extra.js, и показывает фразы, которых в словаре нет. Нужен, чтобы после
правок не приходилось вручную кликать по всем страницам на английском.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = ROOT / "frontend" / "html"
JS_FILES = [ROOT / "frontend" / "js" / "i18n.js", ROOT / "frontend" / "js" / "i18n_extra.js"]

CYRILLIC = re.compile(r"[А-Яа-яЁё]")
TAG = re.compile(r"<[^>]+>")
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
SPACES = re.compile(r"\s+")
# фразы, которые переводить не нужно: демо-код, символы, числа
SKIP_SHORT = 2


def squeeze(text: str) -> str:
    return SPACES.sub(" ", text).strip()


def dictionary_keys() -> set[str]:
    """Все русские фразы из словарей (ключи DICT и I18N_EXTRA)."""
    keys: set[str] = set()
    key_re = re.compile(r'^\s{2,4}"((?:[^"\\]|\\.)*)":', re.MULTILINE)
    for path in JS_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in key_re.finditer(text):
            keys.add(squeeze(match.group(1).replace('\\"', '"')))
    return keys


def template_phrases(path: Path) -> list[str]:
    """Русские фразы шаблона: текст между тегами и значения атрибутов placeholder/title."""
    raw = path.read_text(encoding="utf-8")
    # блоки <style> и <script>, <title> и комментарии Jinja не переводим
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL)
    raw = re.sub(r"<title>.*?</title>", " ", raw, flags=re.DOTALL)
    raw = re.sub(r"\{#.*?#\}", " ", raw, flags=re.DOTALL)
    # block title — это <title> вкладки, его переводит i18n.js по частям («Обучение · Экстренка»)
    raw = re.sub(r"\{%\s*block title\s*%\}.*?\{%\s*endblock\s*%\}", " ", raw, flags=re.DOTALL)
    raw = JINJA.sub(" ", raw)
    phrases: list[str] = []
    for value in re.findall(r'(?:placeholder|title|aria-label)="([^"]+)"', raw):
        if CYRILLIC.search(value):
            phrases.append(squeeze(TAG.sub(" ", value)))
    for chunk in TAG.split(raw):
        text = squeeze(chunk)
        if text and CYRILLIC.search(text) and len(text) > SKIP_SHORT:
            phrases.append(text)
    # уникальные, в порядке появления
    seen: set[str] = set()
    ordered: list[str] = []
    for phrase in phrases:
        if phrase not in seen:
            seen.add(phrase)
            ordered.append(phrase)
    return ordered


def main(argv: list[str]) -> int:
    keys = dictionary_keys()
    only = argv[1] if len(argv) > 1 else None
    total_missing = 0
    for path in sorted(HTML_DIR.glob("*.html")):
        if only and only not in path.name:
            continue
        phrases = template_phrases(path)
        missing = [p for p in phrases if p not in keys]
        total_missing += len(missing)
        mark = "OK " if not missing else "!! "
        print(f"{mark}{path.name}: {len(phrases)} русских фраз, не в словаре {len(missing)}")
        if only:
            for phrase in missing:
                print("     ·", phrase[:150])
    print()
    print("в словаре фраз:", len(keys))
    print("не переведено (фраз в шаблонах без пары):", total_missing)
    return 0 if total_missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
