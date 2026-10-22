"""Локальный запуск проекта — один скрипт для Windows, macOS и Linux.

Что делает:
  1. проверяет версию Python;
  2. создаёт .venv и ставит зависимости (только первый раз);
  3. создаёт .env со случайным SECRET_KEY, если его нет;
  4. создаёт демо-данные, если базы ещё нет;
  5. запускает сервер и открывает браузер.

Использование:
    python run_local.py
    python run_local.py --port 9000     # другой порт
    python run_local.py --no-browser    # не открывать браузер
"""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"
DB_FILE = BASE_DIR / "data" / "app.db"
MIN_PYTHON = (3, 11)


def say(message: str) -> None:
    print(message, flush=True)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def ensure_venv() -> Path:
    """Создаёт виртуальное окружение и ставит зависимости. Возвращает путь к python из venv."""
    python = venv_python()
    if not python.exists():
        say("Создаю виртуальное окружение (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    requirements = BASE_DIR / "requirements.txt"
    marker = VENV_DIR / ".deps-installed"
    if not marker.exists():
        say("Устанавливаю зависимости, первый раз это около минуты...")
        subprocess.check_call([str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        subprocess.check_call([str(python), "-m", "pip", "install", "--quiet", "-r", str(requirements)])
        marker.write_text("ok", encoding="utf-8")
    return python


def ensure_env() -> None:
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
    else:
        text = "APP_NAME=Испытания\nSECRET_KEY=change-me\n"
    text = text.replace("замени-на-длинную-случайную-строку", secrets.token_hex(32))
    text = text.replace("SEED_DEMO=0", "SEED_DEMO=1")
    if "SECRET_KEY=" not in text:
        text += "\nSECRET_KEY=" + secrets.token_hex(32) + "\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    say("Создан .env со случайным SECRET_KEY")


def ensure_demo_data(python: Path) -> None:
    if DB_FILE.exists() and DB_FILE.stat().st_size > 0:
        return
    say("Создаю демо-данные (демо-пользователи и демо-испытание)...")
    subprocess.call([str(python), "-m", "backend.app.seed"], cwd=str(BASE_DIR))


def in_venv(python: Path) -> bool:
    try:
        return Path(sys.executable).resolve() == python.resolve()
    except OSError:
        return False


def serve(port: int, open_browser: bool) -> None:
    """Запускает uvicorn. Вызывается уже из интерпретатора venv."""
    import uvicorn

    from backend.app.main import app

    url = f"http://localhost:{port}"
    say("")
    say("=" * 56)
    say(f"  Приложение запущено:  {url}")
    say("  Документация API:     " + url + "/docs")
    say("")
    say("  Преподаватель: teacher@example.com / teacher123")
    say("  Учащийся:      student@example.com / student123")
    say("")
    say("  Остановить: Ctrl+C или закройте это окно")
    say("=" * 56)
    say("")

    if open_browser:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        say(f"Нужен Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} или новее.")
        say(f"Сейчас запущен Python {sys.version.split()[0]}.")
        say("Скачать: https://www.python.org/downloads/")
        say("При установке на Windows отметьте галочку «Add Python to PATH».")
        if os.name == "nt":
            input("Нажмите Enter, чтобы закрыть окно...")
        return 1

    say(f"Python {sys.version.split()[0]} — ок")

    try:
        python = ensure_venv()
    except subprocess.CalledProcessError as error:
        say("")
        say("Не удалось установить зависимости.")
        say("Проверьте интернет и запустите снова.")
        say(f"Техническая информация: {error}")
        if os.name == "nt":
            input("Нажмите Enter, чтобы закрыть окно...")
        return 1

    ensure_env()
    ensure_demo_data(python)

    if not in_venv(python):
        # перезапускаем себя уже интерпретатором из venv — там есть fastapi и uvicorn
        command = [str(python), str(Path(__file__).resolve()), "--port", str(args.port)]
        if args.no_browser:
            command.append("--no-browser")
        completed = subprocess.call(command, cwd=str(BASE_DIR))
        if completed != 0 and os.name == "nt":
            input("Нажмите Enter, чтобы закрыть окно...")
        return completed

    port = free_port(args.port)
    if port != args.port:
        say(f"Порт {args.port} занят, использую {port}")

    try:
        serve(port, open_browser=not args.no_browser)
    except KeyboardInterrupt:
        say("\nОстановлено.")
    except Exception as error:  # noqa: BLE001
        say("")
        say("Ошибка при запуске сервера:")
        say(str(error))
        say("")
        say("Частая причина — занятый порт. Попробуйте: python run_local.py --port 9000")
        if os.name == "nt":
            input("Нажмите Enter, чтобы закрыть окно...")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
