"""Собирает автономный preview.html: HTML + CSS + JS в одном файле.

Зачем: показать сайт без Python, без сервера и без установки — двойной клик по файлу.
Данные демо-версии живут в localStorage браузера. Настоящее приложение (backend/ + frontend/)
работает отдельно и не затрагивается.

Запуск из корня проекта:  python tools/build_preview.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSS = BASE / "frontend" / "css" / "style.css"
JS = BASE / "frontend" / "js" / "preview_app.js"
OUT = BASE / "preview.html"

HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Экстренка — демо (без сервера)</title>
<style>
{css}
</style>
</head>
<body>
<div id="app"></div>
<script>
{js}
</script>
</body>
</html>
"""


def main() -> None:
    css = CSS.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    OUT.write_text(HTML.format(css=css, js=js), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Готово: {OUT.name} ({size_kb:.0f} КБ) — открывается двойным кликом.")


if __name__ == "__main__":
    main()
