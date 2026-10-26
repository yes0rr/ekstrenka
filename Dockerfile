FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-vision.txt ./
RUN pip install -r requirements.txt

# видеоанализ: тяжёлые зависимости ставим только при сборке с
#   docker build --build-arg WITH_VISION=1 .
ARG WITH_VISION=0
RUN if [ "$WITH_VISION" = "1" ]; then pip install -r requirements-vision.txt; fi

COPY . .

# модель позы (5.6 МБ) — берём из репозитория, при отсутствии качаем
RUN if [ "$WITH_VISION" = "1" ] && [ ! -f backend/models/pose_landmarker_lite.task ]; \
    then python tools/download_pose_model.py; fi

RUN mkdir -p data

EXPOSE 8000
# Timeweb Cloud прокидывает PORT — run.py его читает
CMD ["python", "run.py"]
