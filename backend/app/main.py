"""Точка входа: uvicorn app.main:app"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import FRONTEND_DIR, settings
from .db import init_db
from .deps import render
from .routers import api, auth, pages, vision

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.seed_demo:
        from .seed import seed

        seed()
    # видеоанализ: воркер MediaPipe поднимается только при VISION_ENABLED=1
    from .vision import get_service

    service = get_service()
    service.start()
    yield
    service.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
# фронтенд: статика раздельно по типам
app.mount("/static/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/static/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

app.include_router(auth.router)
app.include_router(api.router)
app.include_router(vision.router)
app.include_router(pages.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    wants_json = request.url.path.startswith("/api") or "application/json" in request.headers.get("accept", "")
    if wants_json:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=303)
    response = render(request, "error.html", None, code=exc.status_code, message=exc.detail)
    response.status_code = exc.status_code
    return response


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok", "app": settings.app_name}
