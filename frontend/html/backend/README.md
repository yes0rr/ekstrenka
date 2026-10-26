# backend

Вся серверная часть: FastAPI, SQLAlchemy, авторизация, API, бизнес-логика проверки.
Интерфейс (шаблоны, CSS, JS) — в `../frontend`.

```
backend/
├── app/
│   ├── main.py        приложение FastAPI, монтирование статики, /healthz
│   ├── config.py      настройки из окружения (.env, DB_*, SECRET_KEY)
│   ├── db.py          engine, SessionLocal, init_db
│   ├── models.py      User, Log, Test, Question, Attempt, Answer
│   ├── security.py    Argon2, подписанные сессионные cookie, запись логов
│   ├── services.py    проверка ответов, пересчёт баллов
│   ├── neural.py      заглушка нейропроверки (точка подключения модели)
│   ├── deps.py        текущий пользователь, проверка ролей, Jinja2
│   ├── seed.py        демо-данные
│   └── routers/
│       ├── auth.py    вход/регистрация/выход, аккаунт, /api/auth/*
│       ├── api.py     /api/tests, /api/attempts, /api/logs, /api/users
│       └── pages.py   рендер HTML-страниц
└── tests/test_flow.py смоук-тест основного сценария
```

Запуск из корня проекта:

```bash
python -m backend.app.seed      # демо-данные
python run.py                   # сервер
python -m pytest backend/tests -q
```

Импорт приложения: `from backend.app.main import app`.
