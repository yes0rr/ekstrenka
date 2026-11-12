"""Проверка ссылок на статику в шаблонах.

Браузер запоминает JS и CSS надолго. Если в ссылке нет `?v=NN`, после обновления сайта
он отдаст старый файл — именно из-за этого страница видеотеста когда-то «не менялась».
Тест следит, чтобы у каждого скрипта и стиля стояла одна и та же версия.
"""
from __future__ import annotations

import re
from pathlib import Path

HTML = Path(__file__).resolve().parents[2] / "frontend" / "html"
ASSET = re.compile(r'(?:src|href)="(/static/(?:js|css)/[^"]+)"')
CURRENT = "21"


def test_every_script_and_style_has_version():
    problems = []
    for path in sorted(HTML.glob("*.html")):
        for url in ASSET.findall(path.read_text(encoding="utf-8")):
            if "?v=" not in url:
                problems.append(f"{path.name}: {url} — без ?v=")
            elif not url.endswith("?v=" + CURRENT):
                problems.append(f"{path.name}: {url} — старая версия, нужна ?v={CURRENT}")
    assert not problems, "ссылки на статику без актуальной версии:\n" + "\n".join(problems)
