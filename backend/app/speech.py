"""Распознавание речи на сервере — необязательная нейросеть (faster-whisper).

Зачем: встроенное в браузер распознавание (Web Speech API) работает не всегда —
в Chrome без сервисов Google оно сразу отдаёт ошибку «network», а в Firefox его нет вовсе.
Тогда звук короткой фразы уходит на наш сервер и распознаётся локально моделью Whisper.

Как включается:
    pip install -r requirements-voice.txt      (faster-whisper, ~200 МБ зависимостей)
    python tools/download_voice_model.py       (модель base, 145 МБ — качается один раз)
    VOICE_ENABLED=1 в .env

Расход: модель base в памяти ~500 МБ, распознавание фразы 2–5 с — около секунды на CPU.
Мало памяти (2 ГБ)? Возьмите tiny: WHISPER_MODEL=tiny (75 МБ, ~250 МБ в памяти).
Аудио НЕ сохраняется: приходит в память, распознаётся, выбрасывается. В лог попадает только текст.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger(__name__)

MODEL_DIR = Path(os.getenv("WHISPER_DIR", Path(__file__).resolve().parent.parent.parent / "models" / "whisper"))
SAMPLE_RATE = 16000  # столько ждёт Whisper
MAX_AUDIO_BYTES = 4 * 1024 * 1024  # 4 МБ — это секунд 30 webm/opus, больше не нужно


def _enabled() -> bool:
    return os.getenv("VOICE_ENABLED", "0").strip().lower() in {"1", "true", "on", "yes"}


def model_name() -> str:
    """tiny — 75 МБ и быстрее, base — 145 МБ и заметно точнее (по умолчанию base)."""
    return os.getenv("WHISPER_MODEL", "base")


def has_dependency() -> bool:
    """Есть ли пакет faster-whisper (без него серверное распознавание недоступно)."""
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def has_model() -> bool:
    """Скачана ли модель (в папку models/whisper)."""
    if not MODEL_DIR.exists():
        return False
    return any(MODEL_DIR.rglob("model.bin"))


def status() -> dict:
    """Что доступно — этим пользуется и страница, и диагностика."""
    return {
        "enabled": _enabled(),
        "dependency": has_dependency(),
        "model": has_model(),
        "model_name": model_name(),
        "available": bool(_enabled() and has_dependency() and has_model()),
        "model_dir": str(MODEL_DIR),
    }


class SpeechService:
    """Ленивая загрузка модели: пока никто не говорит — память не тратится."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                log.info("голос: загружаю модель %s из %s", model_name(), MODEL_DIR)
                self._model = WhisperModel(
                    model_name(),
                    device="cpu",
                    compute_type=os.getenv("WHISPER_COMPUTE", "int8"),
                    download_root=str(MODEL_DIR),
                )
                log.info("голос: модель готова")
        return self._model

    def transcribe(self, audio: bytes, lang: str = "ru") -> dict:
        """Расшифровать короткую запись (webm/opus, ogg, wav, mp4). Возвращает текст и язык."""
        if len(audio) < 512:
            return {"text": "", "language": lang, "seconds": 0.0}
        pcm = decode_to_pcm(audio)
        if pcm.size < SAMPLE_RATE // 4:  # короче четверти секунды распознавать нечего
            return {"text": "", "language": lang, "seconds": 0.0}
        model = self._load()
        segments, info = model.transcribe(
            pcm,
            language=lang if lang in {"ru", "en"} else None,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return {
            "text": text,
            "language": getattr(info, "language", lang),
            "seconds": round(len(pcm) / SAMPLE_RATE, 2),
        }


def decode_to_pcm(audio: bytes) -> "object":
    """Декодировать запись браузера в моно float32 16 кГц — в этом виде Whisper её и ждёт.

    Своё декодирование вместо встроенного в faster-whisper: свежие версии PyAV
    перестали принимать старый аргумент, и встроенный путь падает с TypeError.
    """
    import av
    import numpy as np

    try:
        return _decode_av(audio, av, np)
    except ValueError:
        raise
    except Exception as error:  # PyAV не понял формат — это не наша ошибка, а битая запись
        raise ValueError(f"формат записи не распознан ({error})") from error


def _decode_av(audio: bytes, av, np):
    with av.open(io.BytesIO(audio)) as container:
        if not container.streams.audio:
            return np.zeros(0, dtype=np.float32)
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        chunks = []
        for frame in container.decode(container.streams.audio[0]):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


_service = SpeechService()


def get_service() -> SpeechService:
    return _service


def decode_base64(payload: str) -> bytes:
    """Развернуть «data:audio/webm;base64,....» (или просто base64) в байты.

    Браузер иногда добавляет переводы строк и «=» в конце — чистим.
    Битый base64 не роняет сервер: возвращаем пустые байты, вызывающий код
    ответит 422 «пустая запись».
    """
    if not payload:
        return b""
    raw = payload.split(",", 1)[1] if payload.startswith("data:") and "," in payload else payload
    raw = "".join(raw.split())  # убрать пробелы и переводы строк
    raw += "=" * (-len(raw) % 4)  # добрать выравнивание
    try:
        return base64.b64decode(raw, validate=False)
    except (ValueError, TypeError):
        return b""


def encoded_size(payload: str) -> int:
    """Сколько примерно байт звука в base64 — чтобы отсечь длинную запись до декодирования."""
    if not payload:
        return 0
    raw = payload.split(",", 1)[1] if payload.startswith("data:") and "," in payload else payload
    return len(raw) * 3 // 4
