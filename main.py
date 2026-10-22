"""Точка входа для App Platform / uvicorn: uvicorn main:app"""

from backend.app.main import app  # noqa: F401

__all__ = ["app"]
