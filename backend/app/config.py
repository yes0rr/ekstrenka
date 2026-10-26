"""Конфигурация приложения (всё через переменные окружения — под Timeweb Cloud)."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# backend/app/config.py -> корень проекта
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
load_dotenv(BASE_DIR / ".env")


def _normalize_db_url(url: str) -> str:
    """Timeweb Cloud отдаёт postgres://, SQLAlchemy 2.x хочет postgresql+psycopg://"""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _database_url() -> str:
    """Два способа задать БД:
    1) DATABASE_URL — одна строка подключения;
    2) DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD (+ DB_SSLMODE) — отдельные переменные,
       удобно, если в пароле есть @ : / ? # (кодировать вручную не нужно).
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize_db_url(url)

    host = os.getenv("DB_HOST")
    if host:
        user = quote_plus(os.getenv("DB_USER", "postgres"))
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        name = os.getenv("DB_NAME", "postgres")
        port = os.getenv("DB_PORT", "5432")
        sslmode = os.getenv("DB_SSLMODE", "prefer")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"

    return f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"


class Settings:
    app_name: str = os.getenv("APP_NAME", "Экстренка")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    database_url: str = _database_url()
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    # время жизни сессионной cookie
    session_max_age: int = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))
    # заглушка проверки «нейросетью»: пока 0 — попытки получают статус pending
    neural_enabled: bool = os.getenv("NEURAL_ENABLED", "0") == "1"
    # автосоздание демо-данных при старте (после первого запуска выключить)
    seed_demo: bool = os.getenv("SEED_DEMO", "0") == "1"
    # разрешить регистрацию с ролью «преподаватель» (в проде лучше 0)
    allow_teacher_signup: bool = os.getenv("ALLOW_TEACHER_SIGNUP", "1") == "1"
    # cookie только по HTTPS (на Timeweb включено по умолчанию)
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "0") == "1"

    # ---- видеоанализ (MediaPipe Pose на сервере) ----
    # выключен по умолчанию: пока 0 — кадры не принимаются, mediapipe не нужен
    vision_enabled: bool = os.getenv("VISION_ENABLED", "0") == "1"
    # сколько попыток обрабатывается одновременно; на 2 ГБ сервере — 1
    max_video_sessions: int = int(os.getenv("MAX_VIDEO_SESSIONS", "1"))
    # целевая частота кадров с клиента (15 — рабочий режим, 30 — если позволяет CPU)
    video_fps: int = int(os.getenv("VIDEO_FPS", "15"))
    # размер очереди кадров у воркера: переполнение → выбрасываем самый старый
    frame_buffer: int = int(os.getenv("FRAME_BUFFER", "30"))
    # сколько секунд без кадров считаем обрывом и освобождаем слот
    heartbeat_timeout: float = float(os.getenv("HEARTBEAT_TIMEOUT", "20"))
    # сколько человек максимум ждут в очереди
    queue_limit: int = int(os.getenv("QUEUE_LIMIT", "20"))
    # оценка длительности станции для расчёта «ждать примерно N минут»
    session_eta_sec: float = float(os.getenv("SESSION_ETA_SEC", "240"))
    # путь к модели pose_landmarker_lite.task
    pose_model_path: str = os.getenv(
        "POSE_MODEL_PATH", str(BASE_DIR / "backend" / "models" / "pose_landmarker_lite.task")
    )


settings = Settings()

(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
