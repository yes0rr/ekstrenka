# Экстренка — короткая инструкция по заливке на сервер

Сервер: **45.153.69.132**, код в `/opt/ispytaniya`, сервис `ispytaniya`, venv `/opt/ispytaniya/.venv`.
Все команды — в веб-консоли Timeweb, **по одной строке за раз** (иначе вставка ломается).

---

## 0. Важно про камеру

Браузер даёт доступ к камере **только по `https://` или на `localhost`**.
Сейчас сайт открывается по `http://45.153.69.132` — на таком адресе камера не включится,
а значит и видеоанализ не заработает. Два варианта — см. раздел 4.

---

## 1. Залить код на GitHub

1. Распакуйте `ekstrenka_v9_2026-10-26.zip` → внутри папка `project`.
2. Откройте https://github.com/yes0rr/ekstrenka
3. **Add file → Upload files**.
4. Откройте папку `project`, выделите всё (Ctrl+A) и перетащите в окно браузера.
5. Внизу **Commit changes**, дождитесь окончания.

Файла `.env` в архиве нет специально — на сервере он свой, трогать его не нужно.
Модель `backend/models/pose_landmarker_lite.task` (5,7 МБ) должна уехать вместе с остальными файлами —
GitHub пропускает файлы до 25 МБ через веб.

---

## 2. Обновить сервер (без видеоанализа)

Если видеоанализ пока не нужен — хватит этих трёх строк:

```
cd /opt/ispytaniya && git pull
```
```
chown -R ispytaniya:ispytaniya /opt/ispytaniya
```
```
systemctl restart ispytaniya
```

Сайт работает как раньше: `VISION_ENABLED=0` по умолчанию, `mediapipe` не требуется.

---

## 3. Включить видеоанализ

### 3.1. Подкачать память (один раз)

`pip install` для mediapipe + opencv съедает ~500 МБ, на 2 ГБ без swap процесс может быть убит.
Проверить:

```
free -m
```

Если в строке `Swap` стоит `0` — создать файл подкачки:

```
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

И прописать его навсегда:

```
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 3.2. Поставить системные библиотеки

`mediapipe` тянет за собой `opencv-contrib-python`, а ему нужны системные библиотеки OpenGL.
Без них в логах будет `libGL.so.1: cannot open shared object file` или
`libGLESv2.so.2: cannot open shared object file`.

```
apt-get install -y libgl1 libgles2 libglvnd0 libglx0 libegl1 libglib2.0-0 && ldconfig
```

Занимает ~30 МБ и минуту. Без `libgles2` mediapipe падает на `libGLESv2.so.2 => not found`,
без `libglvnd0` — на `libGL.so.1 => not found`. `ldconfig` обязателен: он обновляет кэш
загрузчика, иначе новый файл не виден процессу

### 3.3. Поставить Python-зависимости

```
/opt/ispytaniya/.venv/bin/pip install -r /opt/ispytaniya/requirements-vision.txt
```

Это ~200 МБ загрузки (mediapipe, opencv, numpy). Идёт 2–5 минут.

> Альтернатива без OpenGL: вместо `opencv-contrib-python` поставить headless-сборку —
> `pip uninstall -y opencv-contrib-python && pip install opencv-python-headless`.
> На сервере это даже правильнее: окна не нужны, библиотека легче.

### 3.4. Проверить, что модель на месте

```
ls -lh /opt/ispytaniya/backend/models/pose_landmarker_lite.task
```

Должно быть ~5,7M. Если файла нет (не залился на GitHub) — скачать:

```
/opt/ispytaniya/.venv/bin/python /opt/ispytaniya/tools/download_pose_model.py
```

### 3.5. Включить в настройках

```
printf 'VISION_ENABLED=1\nMAX_VIDEO_SESSIONS=1\nVIDEO_FPS=15\nHEARTBEAT_TIMEOUT=20\nQUEUE_LIMIT=20\n' >> /opt/ispytaniya/.env
```

### 3.6. Перезапустить

```
chown -R ispytaniya:ispytaniya /opt/ispytaniya && systemctl restart ispytaniya
```

### 3.7. Проверить логи

```
journalctl -u ispytaniya -n 30 --no-pager
```

Ожидаемые строки:

```
backend.app.vision.worker воркер видеоанализа запущен (pid=...)
backend.app.vision.service модель MediaPipe загружена
backend.app.vision.service сервис видеоанализа запущен
```

Если видите `зависимости не установлены: ... libGL.so.1` — не поставлены системные библиотеки,
вернитесь к шагу 3.2 (или поставьте `opencv-python-headless` вместо `opencv-contrib-python`).

Проверка, что сайт живой:

```
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login
```

Должно вывести `200`.

---

## 4. HTTPS для камеры

Без HTTPS камера не включится ни в Chrome, ни в Edge, ни в Safari — это защита браузера,
а не ошибка сайта. Страница должна открываться по `https://`.

### Вариант 0 — нет домена, но нужен HTTPS сегодня (бесплатно, 5 минут)

Сервис `sslip.io` превращает IP в имя: `45.153.69.132` → `45-153-69-132.sslip.io`.
Домен не покупаем, сертификат Let's Encrypt выдаётся на это имя.

```
apt-get install -y certbot python3-certbot-nginx
```
```
certbot --nginx -d 45-153-69-132.sslip.io
```

На вопрос про редирект выбрать **2** (перенаправлять http → https). После этого сайт
открывается по `https://45-153-69-132.sslip.io`, камера работает.

Проверить, что домен уже резолвится (должен вернуть 45.153.69.132):

```
getent hosts 45-153-69-132.sslip.io
```

### Вариант А — есть свой домен (правильно, для показа комиссии)

Направить A-запись домена на `45.153.69.132`, дождаться применения, затем:

```
apt-get install -y certbot python3-certbot-nginx
```
```
certbot --nginx -d ваш-домен.ru
```

Certbot сам допишет nginx и будет продлевать сертификат. Камера заработает.

### Вариант Б — только IP, для демонстрации

В Chrome открыть `chrome://flags/#unsafely-treat-insecure-origin-as-secure`,
добавить `http://45.153.69.132`, выбрать **Enabled**, перезапустить браузер полностью
(не просто закрыть вкладку). Работает только в этом браузере на этом компьютере —
для живого показа подойдёт, для группы студентов нет.

---

## 5. Если что-то пошло не так

Выключить видеоанализ (сайт продолжит работать):

```
sed -i 's/^VISION_ENABLED=1/VISION_ENABLED=0/' /opt/ispytaniya/.env && systemctl restart ispytaniya
```

Посмотреть, что упало:

```
journalctl -u ispytaniya -n 60 --no-pager
```

Если `ImportError: libGL.so.1` — нужны системные библиотеки (шаг 3.2):

```
apt-get install -y libgl1 libglib2.0-0
```

Если `pip install` не находит версию (другой Python на сервере) — поставить без пинов:

```
/opt/ispytaniya/.venv/bin/pip install mediapipe opencv-python-headless numpy
```

---

## 6. Прочее (локально, демо, структура)

- **Посмотреть без установки**: двойной клик по `preview.html` — демо в браузере, без Python.
- **Запустить локально (Windows)**: двойной клик по `start.bat`; вручную — `python run_local.py`.
- **Демо-вход**: `teacher@example.com / teacher123`, `student@example.com / student123`.
- Подробная карта проекта — `STRUCTURE.md`, полный README — `README_PROJECT.md`,
  краткий для команды — `README_PROGRAM.md`.
