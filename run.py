"""Запуск для Timeweb Cloud: python run.py

Читает HOST/PORT из окружения (Timeweb прокидывает PORT автоматически).
"""
import uvicorn

from backend.app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level="info",
    )
