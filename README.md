# Испытания — платформа проведения и проверки испытаний

Каркас без нейросети: база, роли, режимы, интерфейс, прохождение. Нейропроверка вынесена в одну
точку (`app/neural.py`) — подключается позже без переделки остального.

**Стек:** Python 3.12+ · FastAPI · SQLAlchemy 2 · Jinja2 · SQLite локально / PostgreSQL в Timeweb Cloud.

---

## Что уже работает

| Блок | Реализация |
|---|---|
| Пользователи | регистрация/вход, пароли — Argon2, сессия в подписанной cookie (httponly) |
| Роли | `teacher` (проводящий испытание) и `student` (учащийся), переключение роли в админ-разделе |
| Статус | `active` / `blocked` — блокировка пользователя преподавателем |
| Логи | все значимые действия в таблицу `logs`: вход, ошибка входа, создание/правка испытания, ответ, завершение, ручная оценка, IP + User-Agent |
| Результаты | попытки: авто-балл по алгоритму, ручная оценка преподавателем, статус нейропроверки |
| Испытание | название, описание, режим (обучение/тестирование), субъект (человек/имитация предметами), время, критерии, камера/микрофон |
| Вопросы | одиночный выбор, множественный выбор (частичный балл), текстовый с эталоном, текстовый с ручной проверкой; баллы, подсказки |
| Режим обучения | сразу после ответа — верно/неверно, правильный ответ, подсказка |
| Режим тестирования | вердикт по ходу не раскрывается, только по завершении |
| Запросы от сайта | весь фронт работает через JSON API (`/api/...`), можно дергать извне |
| Ручной ввод | текстовые ответы + форма ручной оценки в результатах |
| Камера/микрофон | предпросмотр видео, индикатор уровня микрофона, учёт факта включения и длительности — **запись пока заглушка** (файлы не сохраняются) |
| Нейропроверка | заглушка: попытка получает `neural_status = pending` |

### Сознательно не сделано (следующие шаги)
1. Реальная запись медиа (`MediaRecorder` → файл на диск/S3, `attempt_id` в имени).
2. Сама нейропроверка: расшифровка аудио (ASR) + оценка по критериям → `app/neural.py`.
3. Ограничение по таймеру на сервере (сейчас таймер только в интерфейсе).
4. Восстановление незавершённой попытки после перезагрузки страницы (сейчас создаётся/переиспользуется сервером, но ответы подтягиваются не в UI).

---

## Локальный запуск

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # и поменяйте SECRET_KEY
python -m backend.app.seed      # демо: teacher@example.com / teacher123, student@example.com / student123
python run.py                   # http://localhost:8000
```

Тесты:

```bash
pip install pytest httpx
python -m pytest tests -q
```

---

## Деплой на Timeweb Cloud

Подробная пошаговая инструкция с нуля (GitHub → PostgreSQL → App Platform → первый вход → бэкапы,
обновления, разбор ошибок): **[DEPLOY_TIMEWEB.md](DEPLOY_TIMEWEB.md)**.

Кратко:

1. Код — в GitHub (`.env` в `.gitignore`, в репозиторий не попадает).
2. **Базы данных** → PostgreSQL, регион с приложением, приватная сеть, без публичного IP.
3. **App Platform** → Backend → **FastAPI** → репозиторий, ветка `main`.
   - сборка: `pip3 install --upgrade -r requirements.txt`
   - запуск: `uvicorn main:app --host 0.0.0.0 --port 8000`
   - проверка состояния: `/healthz`
   - приватная сеть — та же, что у базы (потом не меняется)
4. Переменные: `SECRET_KEY`, `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD/DB_SSLMODE=require`
   (или одна `DATABASE_URL`), `NEURAL_ENABLED=0`, `SEED_DEMO=1` на первый запуск,
   `ALLOW_TEACHER_SIGNUP=0`, `COOKIE_SECURE=1`. Шаблон — `env.production.example`.
5. После первого деплоя: войти демо-учёткой → сменить пароль → создать своего преподавателя →
   заблокировать демо-пользователей → `SEED_DEMO=0` и передеплой.

Таблицы создаются автоматически при старте, миграции пока не нужны.
Docker-вариант: `docker build -t ispytaniya . && docker run -p 8000:8000 --env-file .env ispytaniya`.

---

## Структура

Проект разделён на бэкенд и фронтенд:

```
backend/                      # только Python
  app/
    main.py                   точка входа FastAPI, обработчики ошибок, /healthz
    config.py                 настройки из окружения (Timeweb-ready)
    db.py                     engine, сессии, init_db
    models.py                 User, Log, Test, Question, Attempt, Answer
    security.py               Argon2, подписанные cookie, запись логов
    services.py               алгоритм проверки ответов, пересчёт баллов
    neural.py                 ← ЗАГЛУШКА нейропроверки, точка подключения модели
    deps.py                   текущий пользователь, роли, шаблоны Jinja2
    seed.py                   демо-данные
    routers/
      auth.py                 /login /register /logout, /account, /api/auth/*
      api.py                  /api/tests /api/attempts /api/logs /api/users
      pages.py                HTML-страницы кабинетов
  tests/test_flow.py          смоук-тест сценария

frontend/                     # только то, что видит браузер
  html/                       Jinja2-шаблоны (по одному файлу на страницу)
    base.html                 каркас: шапка, навигация, подключение CSS/JS
    login.html register.html  вход и регистрация (отдельные страницы)
    dashboard_teacher.html dashboard_student.html
    teacher_tests.html teacher_test_new.html teacher_test_edit.html
    teacher_results.html teacher_users.html teacher_logs.html
    student_run.html student_attempts.html student_result.html
    account.html error.html
  css/style.css               оформление (без CDN — работает оффлайн)
  js/
    api.js                    общий fetch-помощник (apiFetch, showError)
    test_new.js               создание испытания
    test_edit.js              публикация, вопросы
    student_run.js            прохождение: ответы, таймер, камера/микрофон
    results.js                ручная оценка преподавателем
    users.js                  роли и блокировка

main.py                       обёртка `from backend.app.main import app` (для App Platform)
run.py                        запуск uvicorn с HOST/PORT из окружения
start.sh / start.bat          локальный запуск в один шаг
requirements.txt Dockerfile .env.example env.production.example
```

Статика отдаётся по путям `/static/css/...` и `/static/js/...` (два отдельных mount),
шаблоны читаются из `frontend/html`.

**Как добавить страницу:** положите `frontend/html/my_page.html` с
`{% extends "base.html" %}` → добавьте роут в `backend/app/routers/pages.py` →
клиентский код положите в `frontend/js/my_page.js` и подключите через
`{% block scripts %}<script src="/static/js/my_page.js"></script>{% endblock %}`.
Данные из Python передаются в JS через JSON-блок:
`<script id="my-config" type="application/json">{"id": {{ obj.id }}}</script>`.

### Роли в интерфейсе

- **Преподаватель**: главная (сводка) → «Испытания» (создание, вопросы, публикация) → «Результаты»
  (авто-балл, нейро-статус, ручной балл и комментарий) → «Пользователи» (роли/блокировка) → «Логи».
- **Учащийся**: главная (доступные испытания) → прохождение (вопросы слева, камера/микрофон справа,
  выбор субъекта испытания) → результат с разбором → «Мои попытки».

---

## Как потом подключить нейросеть

1. В `app/neural.py` реализуйте `evaluate_attempt(payload)` — на вход уже приходит всё нужное:
   заголовок испытания, **критерии**, режим, субъект, список ответов и метаданные медиа.
2. Верните `{"status": "done", "score": float, "comment": str, "verdict": "pass"|"fail"}` —
   значение попадёт в `Attempt.neural_status / neural_score / neural_comment` и отобразится
   в результатах и на странице учащегося.
3. Включите `NEURAL_ENABLED=1`.
4. Для голоса/видео: сначала сохраните файл (см. пункт 1 «не сделано»), затем в `neural.py`
   прогоните ASR → текст → оценка по критериям.

Ничего в БД, роутерах или шаблонах менять не потребуется.

## API коротко

```
POST /api/auth/register | /api/auth/login | /api/auth/logout      GET /api/me
GET|POST /api/tests                GET|PATCH|DELETE /api/tests/{id}
POST /api/tests/{id}/questions     PATCH|DELETE /api/questions/{id}
POST /api/attempts                 GET /api/attempts[?test_id=]     GET /api/attempts/{id}
POST /api/attempts/{id}/answers    POST /api/attempts/{id}/media
POST /api/attempts/{id}/finish     POST /api/attempts/{id}/abort
POST /api/attempts/{id}/manual-result
GET /api/logs                      GET /api/users    PATCH /api/users/{id}
GET /healthz                       интерактивная документация: /docs
```

---

## Открыть сайт в два клика — без сервера

В корне лежит **`preview.html`** — весь сайт в одном файле (HTML + CSS + JS внутри).

1. Двойной клик по `preview.html` (или перетащите в окно браузера).
2. Нажмите «Войти» — демо-доступы уже подставлены в поля.

Работает всё то же: вход и регистрация, роли, создание испытаний и вопросов, режимы
обучения/тестирования, прохождение с камерой и микрофоном, результаты с ручной оценкой,
пользователи, журнал действий. Данные лежат в `localStorage` браузера — сервер, Python и БД не нужны.
Сбросить демо к исходному состоянию: ссылка «сбросить демо» внизу страницы.

Ограничения демо (это витрина, а не продакшн): данные только в этом браузере, пароли не хешируются,
нет настоящей БД, нет нейропроверки, нет общей работы нескольких пользователей.

`preview.html` собирается из исходников фронтенда:

```bash
python tools/build_preview.py     # frontend/css/style.css + frontend/js/preview_app.js -> preview.html
node tools/check_preview.js       # 23 проверки логики демо без браузера
```

## Самый быстрый запуск (локально, один шаг)

- **Windows**: дважды кликните `start.bat`
- **macOS / Linux**: `bash start.sh`
- **вручную (любая ОС)**: `python run_local.py`

Скрипт сам создаст окружение `.venv`, поставит зависимости, сгенерирует `.env` со случайным
`SECRET_KEY`, наполнит базу демо-данными, запустит сервер и откроет браузер.
Нужен только установленный Python 3.11+.

Полезные ключи: `python run_local.py --port 9000`, `--no-browser`.
Если порт 8000 занят, свободный подберётся автоматически.

`start.bat` — тонкая ASCII-обёртка (только вызов `run_local.py`). Так сделано специально:
cmd в русской локали ломает UTF-8 текст внутри bat-файла и начинает выполнять строки
как команды. Вся логика поэтому в Python.
