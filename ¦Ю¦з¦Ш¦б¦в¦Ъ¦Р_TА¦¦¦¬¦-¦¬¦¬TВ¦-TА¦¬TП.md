# Очистка репозитория GitHub (yes0rr/ekstrenka)

Проверено 17.11 по факту: скачал репозиторий и сравнил с архивом v33.

| Где | Файлов |
|---|---|
| В репозитории сейчас | **188** |
| В архиве v33 (правильный состав) | **141** |
| Лишних | **48** |
| Не хватает | **1** — `.env.example` |

Все 48 лишних лежат внутри **`frontend/html`** — при загрузке через веб туда вложилась копия всего проекта.
Сайту это не мешает, но в репозитории каша, а `.env.example` (шаблон настроек) наоборот потерялся.

---

## Шаг 1. Удалить `frontend/html` целиком (одна кнопка)

https://github.com/yes0rr/ekstrenka/tree/main/frontend/html → значок **⋯** справа вверху → **Delete directory** → **Commit changes**.

Внутри этой папки 52 файла: 15 настоящих шаблонов и 37 лишних копий (`backend/`, `frontend/`, `tools/`, `main.py`, `run.py`, `requirements*.txt`, `Dockerfile`, `deploy_vps.sh`, `preview.html`, `README.md`, `STRUCTURE.md`, `DEPLOY_*.md`, `env.production.example`, `start*`).

**Важно:** вместе с лишними удалятся и 19 настоящих шаблонов — поэтому сразу после удаления их надо вернуть (шаг 3). Файлы лежат в архиве v33, папка `frontend/html`.

---

## Шаг 2. Удалить старый `run.py` в корне

https://github.com/yes0rr/ekstrenka/blob/main/run.py → **⋯ → Delete file**.
Он дублирует `main.py`, на сервере используется `main.py` (`uvicorn main:app`).

---

## Шаг 3. Залить v33

1. Распаковать `ekstrenka_v33_2026-11-17.zip` → появится папка `project`.
2. https://github.com/yes0rr/ekstrenka → **Add file → Upload files**.
3. Открыть `project`, выделить **всё** (Ctrl+A) и перетащить в окно.
   GitHub через веб принимает не больше 100 файлов за раз, поэтому — **в два приёма**:
   - **первый:** корень (37 файлов) + `.env.example`, `.gitignore`, `.dockerignore` — то есть `main.py`, `requirements*.txt`, `Dockerfile`, `start*`, `deploy_vps.sh`, `README.md`, `STRUCTURE.md`, `DEPLOY_*.md`, `env.production.example`, `ПРОВЕРКА_вопросов_видеотеста.xlsx`, `ЭКСПЕРТ_вопросы_видеотеста.csv`, `ИНСТРУКЦИЯ_преподавателю_видеотест.md` и остальные документы;
   - **второй:** папки `backend/` (34 файла), `frontend/` (56), `tools/` (10), `train_data/` (3), `versions/` (1).
4. Внизу **Commit changes**, дождаться окончания.

Если какой-то файл не влез (GitHub ругается на количество) — заливайте по одной папке за раз.

---

## Шаг 4. Обновить сервер

```
cd /opt/ispytaniya && git pull
```
```
chown -R ispytaniya:ispytaniya /opt/ispytaniya && systemctl restart ispytaniya
```

Проверка, что встало правильно (ожидаем `77 43` — всего вопросов и из них диагностика):

```
cd /opt/ispytaniya && .venv/bin/python -c "from backend.app.quizbank import QUESTIONS; print(len(QUESTIONS), sum(1 for q in QUESTIONS if q.section=='diagnostics'))"
```

И что сервис жив:

```
systemctl is-active ispytaniya && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/login
```
Должно быть `active` и `200`.

---

## Что проверить глазами после заливки

1. Папка `frontend/html` содержит **только** `*.html` (19 штук) — ни `backend`, ни `frontend`, ни `.py` внутри.
2. В корне есть `.env.example` и `.gitignore`.
3. Файла `run.py` в корне нет.
