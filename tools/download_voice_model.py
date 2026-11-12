"""Скачать модель распознавания речи (Whisper) один раз.

Запуск из папки ispytaniya:
    python tools/download_voice_model.py          # base, 145 МБ (по умолчанию)
    python tools/download_voice_model.py tiny     # 75 МБ, если на сервере мало памяти
    python tools/download_voice_model.py small    # 480 МБ, точнее

Модель кладётся в models/whisper — её же читает сервер при VOICE_ENABLED=1.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("WHISPER_MODEL", "base")
    os.environ.setdefault("WHISPER_MODEL", name)
    try:
        from faster_whisper import WhisperModel
    except Exception:
        print("Нет пакета faster-whisper. Сначала: pip install -r requirements-voice.txt")
        return 1

    target = Path(os.getenv("WHISPER_DIR", ROOT / "models" / "whisper"))
    target.mkdir(parents=True, exist_ok=True)
    print(f"Скачиваю модель {name} в {target} ...")
    WhisperModel(name, device="cpu", compute_type="int8", download_root=str(target))
    # настоящие файлы без повторов: в кэше модели лежат и сами файлы, и симлинки на них
    real = {f.resolve() for f in target.rglob("*") if f.is_file()}
    size = sum(f.stat().st_size for f in real) / 1024 / 1024
    print(f"Готово: модель {name}, {size:.0f} МБ. Включите голос: VOICE_ENABLED=1 в .env и перезапустите сервис.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
