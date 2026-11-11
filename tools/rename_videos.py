#!/usr/bin/env python3
"""Переименовать записи по порядку съёмки: s01_01, s01_02, ...

Зачем: телефон называет файлы по дате и времени (VID_20261106_153012.mp4).
Порядок съёмки = порядок в журнале, поэтому достаточно отсортировать по времени
создания и присвоить имена по порядку.

Запуск из корня проекта:
    python tools/rename_videos.py --student s01
    python tools/rename_videos.py --student s01 --dry-run     # только показать, что будет
    python tools/rename_videos.py --student s01 --start 7     # начать нумерацию с 7

Что делает:
  - берёт все видео из train_data/videos/ (mp4, webm, mov, m4v, avi);
  - сортирует по времени съёмки (из имени файла, иначе по дате изменения);
  - переименовывает в s<студент>_<номер>.<родное расширение>;
  - уже переименованные файлы (s01_*) не трогает.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
STAMP = re.compile(r"(20\d{6})[_-]?(\d{6})")


def sort_key(path: Path) -> tuple:
    """Сначала по штампу времени в имени, иначе по дате изменения файла."""
    m = STAMP.search(path.name)
    if m:
        return (0, m.group(1) + m.group(2), path.name)
    return (1, "", path.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", required=True, help="код студента, например s01")
    ap.add_argument("--videos", default=str(ROOT / "train_data" / "videos"))
    ap.add_argument("--start", type=int, default=1, help="с какого номера начать")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    folder = Path(args.videos)
    if not folder.exists():
        print(f"нет папки {folder} — создайте её и положите туда записи")
        return 1

    code = args.student.lower()
    if not re.fullmatch(r"s\d{2,3}", code):
        print("код студента должен быть вида s01, s02, s10 …")
        return 1

    done = {p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and p.stem.startswith(code + "_")}
    fresh = [p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and p not in done]
    fresh.sort(key=sort_key)

    if not fresh:
        print("нечего переименовывать: новых записей нет")
        print(f"уже размечено: {len(done)} файлов ({code}_*)")
        return 0

    num = args.start
    plan = []
    for p in fresh:
        target = folder / f"{code}_{num:02d}{p.suffix.lower()}"
        while target.exists():
            num += 1
            target = folder / f"{code}_{num:02d}{p.suffix.lower()}"
        plan.append((p, target))
        num += 1

    for src, dst in plan:
        print(f"{src.name}  →  {dst.name}")
        if not args.dry_run:
            src.rename(dst)

    print(f"\nвсего: {len(plan)} файлов" + (" (пробный прогон, ничего не менялось)" if args.dry_run else ""))
    print("дальше: заполнить train_data/labels.csv и запустить tools/export_dataset.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
