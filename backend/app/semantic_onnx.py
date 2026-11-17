"""Сравнение смысла ответа и эталона маленькой моделью (ONNX, без torch).

Зачем: правила в answermatch.py закрывают обычный пересказ («давление низкое» вместо
«САД 80–90»). Но если студент говорит совсем своими словами и общих слов с эталоном
почти нет, нужна модель, которая понимает смысл.

Как это устроено:
    ответ и эталон → токенизатор → модель (ONNX) → усреднённый вектор предложения
    → косинус между векторами. Похоже по смыслу — косинус близко к 1.

Что используется: paraphrase-multilingual-MiniLM-L12-v2, версия int8 (113 МБ).
Понимает и русский, и английский. Считается на процессоре через onnxruntime,
torch не нужен. Фраза — примерно 10–20 мс.

Включается флагом SEMANTIC_EMBEDDINGS=1 (по умолчанию выключено: правила и так работают).
Модель качается один раз: python tools/download_semantic_model.py
"""
from __future__ import annotations

import os
from .config import BASE_DIR  # noqa: F401  (при импорте читает .env — флаги видны и из консоли)
import threading
from pathlib import Path

import numpy as np

MODEL_DIR = Path(os.getenv("SEMANTIC_DIR",
                           Path(__file__).resolve().parent.parent.parent / "models" / "semantic"))
MODEL_FILE = MODEL_DIR / "model.onnx"
TOKENIZER_FILE = MODEL_DIR / "tokenizer.json"
MAX_TOKENS = 128

_lock = threading.Lock()
_session = None
_tokenizer = None
_failed = False


def enabled() -> bool:
    """Флаг SEMANTIC_EMBEDDINGS=1 включает модель."""
    return os.getenv("SEMANTIC_EMBEDDINGS", "0").strip().lower() in {"1", "true", "on", "yes"}


def has_files() -> bool:
    """Скачаны ли модель и токенизатор."""
    return MODEL_FILE.exists() and TOKENIZER_FILE.exists()


def has_dependency() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except Exception:
        return False
    return True


def status() -> dict:
    """Для страницы настроек и диагностики на сервере."""
    return {
        "enabled": enabled(),
        "dependency": has_dependency(),
        "model": has_files(),
        "available": enabled() and has_dependency() and has_files(),
        "dir": str(MODEL_DIR),
    }


def _load():
    """Загрузить модель один раз (внутри процесса, потокобезопасно)."""
    global _session, _tokenizer, _failed
    if _session is not None and _tokenizer is not None:
        return _session, _tokenizer
    with _lock:
        if _session is not None and _tokenizer is not None:
            return _session, _tokenizer
        if _failed:
            return None, None
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            options = ort.SessionOptions()
            options.intra_op_num_threads = max(1, min(2, os.cpu_count() or 1))
            _session = ort.InferenceSession(str(MODEL_FILE), options,
                                            providers=["CPUExecutionProvider"])
            _tokenizer = Tokenizer.from_file(str(TOKENIZER_FILE))
            _tokenizer.enable_truncation(max_length=MAX_TOKENS)
            _tokenizer.enable_padding(length=None)
        except Exception:
            _failed = True
            return None, None
    return _session, _tokenizer


def embed(text: str) -> np.ndarray | None:
    """Вектор предложения: среднее по токенам с учётом маски, потом нормировка."""
    session, tokenizer = _load()
    if session is None or not text.strip():
        return None
    encoding = tokenizer.encode(text)
    ids = np.array([encoding.ids], dtype=np.int64)
    mask = np.array([encoding.attention_mask], dtype=np.int64)
    types = np.array([encoding.type_ids], dtype=np.int64)
    names = {i.name for i in session.get_inputs()}
    feed = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in names:
        feed["token_type_ids"] = types
    outputs = session.run(None, feed)
    hidden = outputs[0]                      # (1, токены, 384)
    weights = mask[0][:, None].astype(np.float32)
    vector = (hidden[0] * weights).sum(axis=0) / np.clip(weights.sum(), 1e-6, None)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


def similarity(answer: str, reference: str) -> float:
    """Косинус между ответом и эталоном, 0…1 (для текстов на русском/английском)."""
    try:
        a = embed(answer)
        b = embed(reference)
        if a is None or b is None:
            return 0.0
        return float(max(0.0, min(1.0, float(np.dot(a, b)))))
    except Exception:
        return 0.0
