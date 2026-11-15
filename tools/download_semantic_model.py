"""Скачать маленькую модель сравнения смысла (ONNX) — один раз, если нужна нейропроверка.

Запуск из папки ispytaniya:
    python tools/download_semantic_model.py

Что качается: paraphrase-multilingual-MiniLM-L12-v2 (int8, 113 МБ) + токенизатор (16 МБ)
в models/semantic. Понимает и русский, и английский; работает на процессоре через onnxruntime,
torch не требуется.

Включается флагом SEMANTIC_EMBEDDINGS=1 в .env. Без флага сервер проверяет ответы правилами
(backend/app/answermatch.py) и модель не загружает.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = os.getenv("SEMANTIC_REPO", "Xenova/paraphrase-multilingual-MiniLM-L12-v2")
FILES = {
    "model.onnx": "onnx/model_int8.onnx",
    "tokenizer.json": "tokenizer.json",
    "tokenizer_config.json": "tokenizer_config.json",
}


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {target.name}: {done * 100 // total}%", end="", flush=True)
    temp.replace(target)
    print(f"\r  {target.name}: готово, {target.stat().st_size / 1048576:.0f} МБ")


def main() -> int:
    target_dir = Path(os.getenv("SEMANTIC_DIR", ROOT / "models" / "semantic"))
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Модель: {REPO}\nПапка:  {target_dir}")
    for name, remote in FILES.items():
        target = target_dir / name
        if target.exists() and target.stat().st_size > 0:
            print(f"  {name}: уже есть, {target.stat().st_size / 1048576:.0f} МБ")
            continue
        url = f"https://huggingface.co/{REPO}/resolve/main/{remote}"
        try:
            _download(url, target)
        except Exception as error:
            print(f"\nНе удалось скачать {remote}: {error}")
            return 1
    print("\nГотово. Включите проверку по смыслу: SEMANTIC_EMBEDDINGS=1 в .env и перезапустите сервис.")
    print("Проверка: .venv/bin/python -c \"from backend.app import semantic_onnx; print(semantic_onnx.status())\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
