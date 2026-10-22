# frontend

Всё, что видит браузер. Бэкенд лежит в `../backend`.

```
frontend/
├── html/     Jinja2-шаблоны, по файлу на страницу
├── css/      style.css — единственный файл оформления, без CDN
└── js/       скрипты по страницам, api.js — общий помощник
```

Как это связано:

| Файл | Кто рендерит | Откуда данные |
|---|---|---|
| `html/*.html` | Jinja2 на сервере (`backend/app/deps.py` → `FRONTEND_DIR / "html"`) | контекст из `backend/app/routers/pages.py` |
| `css/*.css` | отдаётся по `/static/css/...` | — |
| `js/*.js` | отдаётся по `/static/js/...` | через JSON-блок в шаблоне и запросы к `/api/...` |

Правила, которых придерживаемся:

1. **HTML — только разметка.** Никакого `<script>` с логикой внутри: скрипт лежит файлом
   в `js/` и подключается в `{% block scripts %}`.
2. **Данные из Python в JS** передаются одним JSON-блоком, а не набором подстановок:
   ```html
   <script id="run-config" type="application/json">{"testId": {{ test.id }}, "total": {{ n }}}</script>
   ```
   В JS: `const cfg = JSON.parse(document.getElementById('run-config').textContent);`
3. **Сетевые вызовы** — только через `apiFetch()` из `js/api.js`: он сам разбирает JSON,
   кидает ошибку с понятным текстом и закрывает типовые случаи.
4. **Стили** — общий `css/style.css`, классы переиспользуются (`.panel`, `.btn`, `.tag`, `.grid`).
   Если файл вырастет, делим на `base.css`, `components.css`, `pages.css` — точки подключения
   в `base.html` и `login.html`/`register.html` (у них отдельный каркас).

Добавить новую страницу:

1. `frontend/html/my_page.html` — `{% extends "base.html" %}` и блок `content`.
2. `backend/app/routers/pages.py` — роут, который рендерит шаблон через `render(...)`.
3. `frontend/js/my_page.js` — логика; подключить в `{% block scripts %}`.
