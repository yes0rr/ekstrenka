#!/usr/bin/env bash
# Запуск проекта локально (macOS / Linux). Вся логика — в run_local.py.
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 run_local.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python run_local.py "$@"
else
  echo "Не найден Python 3.11+."
  echo "Установите: https://www.python.org/downloads/ (macOS: brew install python)"
  exit 1
fi
