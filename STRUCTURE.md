# Структура проекта «Испытания»

Актуально на текущую версию. Генерируется по реальному содержимому папки.

```
ispytaniya/
│
├── preview.html               ← ВЕСЬ САЙТ В ОДНОМ ФАЙЛЕ. Двойной клик — работает без сервера
│                                 (демо-витрина, данные в localStorage браузера)
│
├── backend/                   ТОЛЬКО PYTHON — серверная часть
│   ├── app/
│   │   ├── main.py            точка входа FastAPI: роутеры, статика, /healthz, ошибки
│   │   ├── config.py          настройки из .env: SECRET_KEY, DB_*, режимы
│   │   ├── db.py              подключение к БД, сессии, init_db (создаёт таблицы)
│   │   ├── models.py          таблицы: User, Log, Test, Question, Attempt, Answer
│   │   ├── security.py        Argon2 (пароли), сессионные cookie, запись логов
│   │   ├── services.py        проверка ответов алгоритмом, пересчёт баллов
│   │   ├── neural.py          ЗАГЛУШКА нейропроверки — сюда придёт модель
│   │   ├── deps.py            текущий пользователь, проверка ролей, Jinja2
│   │   ├── seed.py            демо-данные (2 пользователя + демо-испытание)
│   │   └── routers/
│   │       ├── auth.py        /login /register /logout /account + /api/auth/*
│   │       ├── api.py         /api/tests /api/attempts /api/logs /api/users
│   │       └── pages.py       рендер HTML-страниц (кабинеты, испытания, результаты)
│   ├── tests/test_flow.py     смоук-тест: вход, роли, прохождение, оценка
│   └── README.md              карта бэкенда
│
├── frontend/                  ТОЛЬКО ТО, ЧТО ВИДИТ БРАУЗЕР
│   ├── html/                  16 шаблонов Jinja2, по файлу на страницу
│   │   ├── base.html          каркас: шапка, навигация, подключение CSS/JS
│   │   ├── login.html         вход (отдельный каркас, без шапки)
│   │   ├── register.html      регистрация + выбор роли
│   │   ├── account.html       профиль и смена пароля
│   │   ├── dashboard_teacher.html   главная преподавателя (сводка)
│   │   ├── dashboard_student.html   главная учащегося (доступные испытания)
│   │   ├── teacher_tests.html       список моих испытаний
│   │   ├── teacher_test_new.html    создание испытания
│   │   ├── teacher_test_edit.html   вопросы, публикация
│   │   ├── teacher_results.html     результаты + ручная оценка
│   │   ├── teacher_users.html       роли, блокировка
│   │   ├── teacher_logs.html        журнал действий
│   │   ├── student_run.html         прохождение: вопросы, камера, микрофон
│   │   ├── student_attempts.html    мои попытки
│   │   ├── student_result.html      результат с разбором
│   │   └── error.html               403/404 и прочие
│   ├── css/
│   │   └── style.css          всё оформление (тёмная тема, без CDN)
│   ├── js/
│   │   ├── api.js             общий помощник: apiFetch(), showError() — подключается везде
│   │   ├── test_new.js        создание испытания
│   │   ├── test_edit.js       публикация, добавление/удаление вопросов
│   │   ├── student_run.js     прохождение: ответы, таймер, камера/микрофон
│   │   ├── results.js         ручная оценка преподавателем
│   │   ├── users.js           смена роли, блокировка
│   │   └── preview_app.js     логика демо-версии для preview.html
│   └── README.md              соглашения по фронтенду
│
├── tools/
│   ├── build_preview.py       собирает preview.html из css + preview_app.js
│   └── check_preview.js       23 проверки логики демо без браузера (node)
│
├── data/                      SQLite-база локально (app.db создаётся сама)
│
├── main.py                    обёртка `from backend.app.main import app` для Timeweb
├── run.py                     запуск через uvicorn (используется на сервере)
├── run_local.py               ← ЗАПУСК НА СВОЁМ КОМПЬЮТЕРЕ: venv, зависимости, .env, демо, сервер
├── start.bat                  двойной клик в Windows → вызывает run_local.py (ASCII, CRLF)
├── start.sh                   то же для macOS/Linux
│
├── requirements.txt           зависимости Python
├── Dockerfile                 образ для деплоя в контейнере
├── .env.example               шаблон локальных настроек
├── env.production.example     шаблон переменных для Timeweb Cloud
├── .gitignore .dockerignore   что не попадает в git и в Docker-образ
│
├── README.md                  обзор проекта, запуск, структура
└── DEPLOY_TIMEWEB.md          деплой на Timeweb Cloud с нуля, по шагам
```

---

## Что с чем связано

**Три способа запустить — три разных входа:**

| Хочу | Что открыть | Нужен Python | Данные |
|---|---|---|---|
| Просто посмотреть сайт | `preview.html` | нет | в браузере (localStorage) |
| Работать по-настоящему у себя | `start.bat` (Win) / `bash start.sh` / `python run_local.py` | да | SQLite в `data/app.db` |
| Дать ссылку другим | деплой по `DEPLOY_TIMEWEB.md` | нет (в облаке) | PostgreSQL в Timeweb |

**Поток одного действия (например, «студент ответил на вопрос»):**

```
frontend/html/student_run.html      разметка страницы
        ↓ подключает
frontend/js/student_run.js          ловит клик, отправляет запрос
        ↓ через
frontend/js/api.js                  apiFetch('/api/attempts/5/answers')
        ↓ HTTP
backend/app/routers/api.py          принимает запрос, проверяет права
        ↓
backend/app/services.py             сверяет ответ с правильным, считает баллы
        ↓
backend/app/models.py               сохраняет Answer + Attempt в БД
        ↓
backend/app/security.py             пишет запись в таблицу logs
        ↓ ответ JSON
frontend/js/student_run.js          показывает «Верно / Неверно» (только режим обучения)
```

**Кто за что отвечает:**

- `backend/app/routers/` — «двери» приложения. `pages.py` отдаёт HTML, `api.py` отдаёт JSON, `auth.py` — вход и аккаунт. Сами ничего не считают, вызывают сервисы.
- `backend/app/services.py` — вся логика проверки: одиночный выбор, множественный (частичный балл), текстовый с эталоном, ручная проверка.
- `backend/app/models.py` — единственное место, где описан формат данных. Меняете поле → смотрите сюда.
- `backend/app/neural.py` — одна функция `evaluate_attempt()`. Когда появится модель, правится только этот файл и переменная `NEURAL_ENABLED`.
- `frontend/html/` — только разметка, без логики. Каждая страница наследует `base.html`.
- `frontend/js/` — по файлу на страницу + общий `api.js`. Скрипты подключаются в `{% block scripts %}`.
- `frontend/css/style.css` — один файл на весь сайт: `.panel`, `.btn`, `.tag`, `.grid` переиспользуются.
- `tools/` — обслуживание демо: сборка `preview.html` и его автопроверка. На работу сайта не влияют.

**Где что менять:**

| Задача | Файл |
|---|---|
| Новая страница | `frontend/html/*.html` + роут в `backend/app/routers/pages.py` |
| Новое поле в испытании/попытке | `backend/app/models.py` (+ `api.py`, шаблоны) |
| Другая логика оценки | `backend/app/services.py` |
| Подключить нейросеть | `backend/app/neural.py` + `NEURAL_ENABLED=1` |
| Другой вид кнопок/панелей | `frontend/css/style.css` |
| Переменные окружения | `.env` (локально) или панель Timeweb |
| Обновить демо-файл | `frontend/js/preview_app.js` → `python tools/build_preview.py` |

**Важно про `preview.html`:** он собирается из `frontend/css/style.css` и `frontend/js/preview_app.js`.
Руками его не правят — изменения потеряются при следующей сборке.
