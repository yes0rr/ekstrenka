"""Подключение к БД и сессии SQLAlchemy."""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: сессия БД на один запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# новые колонки, которые могли появиться после первого создания базы
_ADDED_COLUMNS = {
    "attempts": {
        "vision_status": "VARCHAR(20) DEFAULT 'off' NOT NULL",
        "vision_data": "TEXT",
    },
}


def _ensure_added_columns() -> None:
    """Дописать новые колонки в уже существующие таблицы.

    create_all() не меняет созданные таблицы, поэтому при обновлении проекта
    на работающем сервере колонки добавляем здесь. Операция идемпотентна.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _ADDED_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in present:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    from . import models  # noqa: F401  (нужно, чтобы описались таблицы)

    Base.metadata.create_all(bind=engine)
    _ensure_added_columns()
