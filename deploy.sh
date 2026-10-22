#!/usr/bin/env bash
# Установка «Испытаний» на чистый сервер (Ubuntu/Debian) одной командой.
#
#   bash deploy.sh
#
# Скрипт сам: ставит Python/nginx/PostgreSQL, создаёт базу и пользователя,
# генерирует пароли, забирает код из Git, поднимает сервис и настраивает nginx.
# Пароль БД и SECRET_KEY генерируются автоматически и выводятся в конце.
set -euo pipefail

REPO="${REPO:-https://github.com/yes0rr/ekstrenka.git}"
APP_DIR="/opt/ispytaniya"
APP_USER="ispytaniya"
DB_NAME="ispytaniya"
DB_USER="ispytaniya"
DB_PASS="$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Запускать нужно от root. Выполните: sudo bash deploy.sh"
  exit 1
fi

say "1/8 Устанавливаю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx postgresql curl >/dev/null

say "2/8 Создаю базу данных PostgreSQL"
systemctl enable --now postgresql >/dev/null 2>&1 || true
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" >/dev/null
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" >/dev/null
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null

say "3/8 Забираю код из Git"
if [ -d "${APP_DIR}/.git" ]; then
  git -C "${APP_DIR}" pull --ff-only
else
  rm -rf "${APP_DIR}"
  git clone --depth 1 "${REPO}" "${APP_DIR}"
fi

say "4/8 Создаю системного пользователя и виртуальное окружение"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

say "5/8 Пишу .env"
mkdir -p "${APP_DIR}/data"
cat > "${APP_DIR}/.env" <<ENVFILE
APP_NAME=Испытания
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
NEURAL_ENABLED=0
SEED_DEMO=1
ALLOW_TEACHER_SIGNUP=1
COOKIE_SECURE=0
SESSION_MAX_AGE=604800
ENVFILE
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

say "6/8 Создаю демо-данные"
sudo -u "${APP_USER}" env HOME="${APP_DIR}" "${APP_DIR}/.venv/bin/python" -m backend.app.seed || true

say "7/8 Настраиваю systemd-сервис"
cat > /etc/systemd/system/ispytaniya.service <<UNIT
[Unit]
Description=Испытания (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ispytaniya >/dev/null 2>&1
systemctl restart ispytaniya

say "8/8 Настраиваю nginx"
cat > /etc/nginx/sites-available/ispytaniya <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 200M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/ispytaniya /etc/nginx/sites-enabled/ispytaniya
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 && systemctl reload nginx

sleep 3
IP="$(curl -s --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')"

printf '\n\033[1;32m=========================================================\033[0m\n'
printf ' Установка завершена\n'
printf '\033[1;32m=========================================================\033[0m\n'
printf ' Сайт:        http://%s\n' "${IP}"
printf ' Проверка:    %s\n' "$(curl -s --max-time 5 http://127.0.0.1:8000/healthz || echo 'НЕ ОТВЕЧАЕТ — смотрите журнал')"
printf '\n Логин: teacher@example.com / teacher123  (смените пароль!)\n'
printf '        student@example.com / student123\n'
printf '\n Пароль базы (сохраните):  %s\n' "${DB_PASS}"
printf ' SECRET_KEY:               %s\n' "${SECRET_KEY}"
printf '\n Дальше включите HTTPS, иначе камера не заработает:\n'
printf '   apt-get install -y certbot python3-certbot-nginx\n'
printf '   certbot --nginx -d ВАШ-ДОМЕН\n'
printf ' после этого поставьте COOKIE_SECURE=1 в %s/.env и:\n' "${APP_DIR}"
printf '   systemctl restart ispytaniya\n'
printf '\n Полезное:\n'
printf '   systemctl status ispytaniya\n'
printf '   journalctl -u ispytaniya -n 50\n'
printf '   cd %s && git pull && systemctl restart ispytaniya\n' "${APP_DIR}"
printf '\033[1;32m=========================================================\033[0m\n'
