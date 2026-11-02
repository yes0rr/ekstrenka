#!/usr/bin/env python3
"""Видео → числа: превратить записи попыток в таблицу признаков для обучения.

Зачем: модель не должна смотреть видео. Прогоняем записи через MediaPipe Pose
офлайн (тем же кодом, что и на сервере), получаем на каждую попытку строку чисел.

Запуск (из корня проекта):
    python tools/export_dataset.py

Что читает:
    train_data/labels.csv      разметка эксперта (см. train_data/README.md)
    train_data/videos/*.mp4    записи попыток (webm, mp4, avi)

Что пишет:
    train_data/dataset.csv          признаки + метки: вход для train_model.py
    train_data/skeletons/<id>.json  скелет (33 точки) — для повтора без лиц, --save-skeletons

Флаги:
    --labels PATH     другая разметка
    --videos PATH     другая папка с видео
    --out PATH        другой файл датасета
    --fps 15          частота выборки кадров (на сервере тоже 15)
    --limit 10        обработать только первые N записей (быстрая проверка)
    --save-skeletons  сохранить скелеты для повтора
    --force           перезаписать уже посчитанные строки (по умолчанию пропускаем)

Зависимости: pip install -r requirements-train.txt
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dataset_schema import FEATURES, LABELS, META  # noqa: E402


def load_geometry():
    """Загрузить geometry.py напрямую по файлу.

    Почему не `from backend.app.vision.geometry import ...`: пакет vision тянет за собой
    config и dotenv, и скрипт требовал бы всё окружение сервера. Нам нужна только
    математика по точкам — берём один файл, без зависимостей.
    """
    import importlib.util

    path = ROOT / "backend" / "app" / "vision" / "geometry.py"
    spec = importlib.util.spec_from_file_location("vision_geometry", path)
    module = importlib.util.module_from_spec(spec)
    # регистрируем в sys.modules ДО выполнения: иначе @dataclass внутри файла падает
    sys.modules["vision_geometry"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module

MODEL_PATH = ROOT / "backend" / "models" / "pose_landmarker_lite.task"
VIDEO_EXT = {".mp4", ".webm", ".avi", ".mkv", ".mov"}


# ------------------------------------------------------------------ вспомогательное
def die(text: str) -> None:
    print(f"\n[ошибка] {text}", file=sys.stderr)
    raise SystemExit(1)


def read_labels(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        die(
            f"нет файла разметки {path}\n"
            "Скопируйте шаблон: cp train_data/labels.example.csv train_data/labels.csv"
        )
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        die(f"{path} пустой")
    missing = [c for c in ("id", "file", "student") if c not in rows[0]]
    if missing:
        die(f"в {path} нет столбцов: {', '.join(missing)}")
    return rows


def resolve_video(row: dict[str, str], videos_dir: Path) -> Path | None:
    name = (row.get("file") or "").strip()
    if not name:
        return None
    candidate = Path(name)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (videos_dir, videos_dir.parent):
        p = base / name
        if p.exists():
            return p
    # ищем по имени без расширения: запись могла сохраниться как .webm
    stem = candidate.stem
    for p in videos_dir.glob(stem + ".*"):
        if p.suffix.lower() in VIDEO_EXT:
            return p
    return None


def avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    return round(sum(clean) / len(clean), 2) if clean else None


# ------------------------------------------------------------------ обработка одного видео
def process_video(path: Path, fps: float, save_skeletons: bool,
                  skeleton_dir: Path, record_id: str) -> dict[str, Any] | None:
    """Прогнать видео через MediaPipe и вернуть признаки одной попытки."""
    import cv2  # локальный импорт: без opencv скрипт падает понятной ошибкой ниже
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    geometry = load_geometry()
    SessionAggregator, frame_metrics = geometry.SessionAggregator, geometry.frame_metrics

    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
    )
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        print(f"  ! не открывается видео {path.name}")
        return None

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(src_fps / fps))  # берём каждый N-й кадр

    agg = SessionAggregator()
    collect = {
        "arm_left_deg": [], "arm_right_deg": [], "vertical_deg": [],
        "hands_together_cm": [], "side_ratio": [], "wrists_y": [],
    }
    skeleton: list[dict[str, Any]] = []

    idx = 0
    used = 0
    ts_ms = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step:
            idx += 1
            continue
        idx += 1
        used += 1
        ts_ms = int(used * 1000 / fps)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms
        )
        if res.pose_landmarks:
            lm = res.pose_landmarks[0]
            world = res.pose_world_landmarks[0] if res.pose_world_landmarks else None
            fm = frame_metrics(lm, world)
            fm["pose"] = True
            for key in collect:
                value = fm.get(key)
                if isinstance(value, (int, float)):
                    collect[key].append(float(value))
            if save_skeletons:
                skeleton.append({
                    "t": round(used / fps, 3),
                    "points": [[round(float(p.x), 4), round(float(p.y), 4),
                                round(float(p.z), 4)] for p in lm],
                })
        else:
            fm = {"pose": False}

        agg.add_frame(used / fps, fm)

    cap.release()
    landmarker.close()

    if not used:
        print("  ! в видео нет кадров")
        return None

    summary = agg.summary()
    features: dict[str, Any] = {
        "tempo_bpm": summary.get("tempo_bpm"),
        "depth_cm": summary.get("depth_cm"),
        "rhythm_cv": summary.get("rhythm_cv"),
        "compressions": summary.get("compressions"),
        "arms_straight_pct": summary.get("arms_straight_pct"),
        "arms_vertical_pct": summary.get("arms_vertical_pct"),
        "hands_together_pct": summary.get("hands_together_pct"),
        "hands_on_midline_pct": summary.get("hands_on_midline_pct"),
        "side_view_pct": summary.get("side_view_pct"),
        "pose_ratio": round(summary.get("frames_with_pose", 0) / used, 3),
        "duration_s": summary.get("duration_s"),
        "arm_left_mean_deg": avg(collect["arm_left_deg"]),
        "arm_right_mean_deg": avg(collect["arm_right_deg"]),
        "arm_min_deg": round(min(collect["arm_left_deg"] + collect["arm_right_deg"]), 1)
        if collect["arm_left_deg"] or collect["arm_right_deg"] else None,
        "vertical_mean_deg": avg(collect["vertical_deg"]),
        "hands_gap_cm": avg(collect["hands_together_cm"]),
        "side_ratio_mean": avg(collect["side_ratio"]),
        "wrists_amp": round(max(collect["wrists_y"]) - min(collect["wrists_y"]), 4)
        if len(collect["wrists_y"]) > 2 else None,
    }

    if save_skeletons and skeleton:
        skeleton_dir.mkdir(parents=True, exist_ok=True)
        (skeleton_dir / f"{record_id}.json").write_text(
            json.dumps(skeleton, ensure_ascii=False), encoding="utf-8"
        )

    features["_frames_used"] = used
    features["_frames_with_pose"] = summary.get("frames_with_pose", 0)
    return features


# ------------------------------------------------------------------ главное
def main() -> int:
    parser = argparse.ArgumentParser(description="Видео попыток → таблица признаков")
    parser.add_argument("--labels", default=str(ROOT / "train_data" / "labels.csv"))
    parser.add_argument("--videos", default=str(ROOT / "train_data" / "videos"))
    parser.add_argument("--out", default=str(ROOT / "train_data" / "dataset.csv"))
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--save-skeletons", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    videos_dir = Path(args.videos)
    out_path = Path(args.out)
    skeleton_dir = out_path.parent / "skeletons"

    if not MODEL_PATH.exists():
        die(
            f"нет модели {MODEL_PATH}\n"
            "Скачайте: python tools/download_pose_model.py"
        )
    try:
        import cv2  # noqa: F401
        import mediapipe  # noqa: F401
    except ImportError as exc:
        die(
            f"не установлены зависимости ({exc}).\n"
            "Поставьте: pip install -r requirements-train.txt\n"
            "На Linux дополнительно: apt-get install -y libgl1 libglib2.0-0 libgles2 libglvnd0 libglx0 libegl1"
        )

    rows = read_labels(labels_path)
    if args.limit:
        rows = rows[: args.limit]

    # уже посчитанные id — чтобы не гонять повторно
    done: dict[str, dict[str, Any]] = {}
    if out_path.exists() and not args.force:
        with out_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                done[row["id"]] = row
        print(f"уже посчитано ранее: {len(done)} строк (пересчитать: --force)")

    header = META + LABELS + FEATURES
    results: list[dict[str, Any]] = []
    skipped: list[str] = []

    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    for n, row in enumerate(rows, start=1):
        rid = (row.get("id") or "").strip()
        if not rid:
            continue
        if rid in done:
            results.append(done[rid])
            continue

        print(f"[{n}/{len(rows)}] {rid}", end=" ")
        video = resolve_video(row, videos_dir)
        if video is None:
            print("— видео не найдено")
            skipped.append(rid)
            continue

        print(f"— {video.name}", end=" ", flush=True)
        t0 = time.time()
        try:
            features = process_video(video, args.fps, args.save_skeletons, skeleton_dir, rid)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  ! сбой обработки: {exc}")
            skipped.append(rid)
            continue
        if features is None:
            skipped.append(rid)
            continue
        print(
            f"— {features['_frames_used']} кадров, поза в {features['_frames_with_pose']}, "
            f"темп {features.get('tempo_bpm')}, глубина {features.get('depth_cm')} "
            f"({time.time() - t0:.1f} с)"
        )

        record: dict[str, Any] = {key: row.get(key, "") for key in META}
        for label in LABELS:
            record[label] = row.get(label, "")
        for feature in FEATURES:
            value = features.get(feature)
            record[feature] = "" if value is None else value
        results.append(record)

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for record in results:
            writer.writerow({key: record.get(key, "") for key in header})

    print("\n" + "=" * 60)
    print(f"готово за {time.time() - started:.0f} с")
    print(f"строк в датасете: {len(results)} → {out_path}")
    if skipped:
        print(f"пропущено (нет видео или сбой): {len(skipped)} — {', '.join(skipped[:10])}"
              + (" …" if len(skipped) > 10 else ""))
    print("дальше: python tools/train_model.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
