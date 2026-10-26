#!/usr/bin/env python3
"""Скачать модель позы MediaPipe (5.6 МБ) в backend/models/.

Запускать один раз — локально или на шаге сборки:
    python tools/download_pose_model.py

Модель нужна только при VISION_ENABLED=1. В репозиторий её можно не класть,
но тогда этот скрипт должен выполняться при сборке/старте.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
       "pose_landmarker_lite/float16/1/pose_landmarker_lite.task")
TARGET = Path(__file__).resolve().parents[1] / "backend" / "models" / "pose_landmarker_lite.task"


def main() -> int:
    if TARGET.exists() and TARGET.stat().st_size > 1_000_000:
        print(f"модель уже на месте: {TARGET} ({TARGET.stat().st_size / 1e6:.1f} МБ)")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    print(f"качаю {URL}\n     → {TARGET}")
    try:
        urllib.request.urlretrieve(URL, TARGET)
    except Exception as exc:  # noqa: BLE001
        print(f"не получилось: {exc}", file=sys.stderr)
        print("скачайте файл вручную и положите по пути выше", file=sys.stderr)
        return 1
    print(f"готово: {TARGET.stat().st_size / 1e6:.1f} МБ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
