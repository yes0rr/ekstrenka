# Экстренка — короткая инструкция

## 1. Посмотреть без установки

Откройте `preview.html` двойным кликом — работает демо в браузере, без Python и сервера.

## 2. Запустить по-настоящему на своём компьютере

Windows: двойной клик по `start.bat`.
Вручную: `python run_local.py` → откроется http://127.0.0.1:9000

Демо-вход:

| Роль | Почта | Пароль |
|---|---|---|
| преподаватель | teacher@example.com | teacher123 |
| учащийся | student@example.com | student123 |

## 3. Обновить проект на GitHub

1. Распакуйте архив — получится папка `ekstrenka`.
2. Откройте https://github.com/yes0rr/ekstrenka
3. Кнопка **Add file → Upload files**.
4. Выделите в папке `ekstrenka` всё (Ctrl+A) и перетащите в окно браузера.
5. Внизу нажмите **Commit changes** и дождитесь окончания загрузки.

Файла `.env` в архиве нет специально — на сервере он уже создан, трогать его не нужно.

## 4. Обновить сайт на сервере (45.153.69.132)

Веб-консоль Timeweb, по **одной** строке за раз:

```
git config --global --add safe.directory /opt/ispytaniya
```
```
cd /opt/ispytaniya && git pull
```
```
chown -R ispytaniya:ispytaniya /opt/ispytaniya && systemctl restart ispytaniya
```

Проверка:

```
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login
```

Должно вывести `200`. Готово.

## 5. Что в проекте

```
backend/app/     FastAPI, модели, роутеры, БД, заглушка нейропроверки
frontend/html/   шаблоны страниц
frontend/css/    стили (включая мобильную адаптацию)
frontend/js/     скрипты (меню, авторизация, камера)
preview.html     автономное демо без сервера
run_local.py     запуск на своём компьютере
run.py           запуск как на сервере
DEPLOY_TIMEWEB.md подробная инструкция по серверу
```

Нейросети внутри нет — вместо неё заглушка в `backend/app/neural.py`.
