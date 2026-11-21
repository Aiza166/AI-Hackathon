"""Speech: text-to-speech (Azure neural voices) and short speech-to-text.

TTS reads fixed prompts and reasons aloud in Urdu (ur-PK-UzmaNeural) or English.
Audio is cached by sha256(voice + text) in memory (LRU) and optionally on disk, so a
prompt is synthesised once. Without Azure keys: 503 TTS_NOT_CONFIGURED, and the PWA
falls back to the phone's own speech engine. STT only pre-fills a field the user then
confirms; it never decides anything.
"""
import hashlib
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Depends, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.core.auth import Principal, require_roles
from app.core.config import Settings, get_settings
from app.core.envelope import fail, ok
from app.core.ratelimit import limiter
from app.schemas.contracts import Role

log = logging.getLogger("sahara.speech")
router = APIRouter(prefix="/api/v1/speech", tags=["speech"])

VOICES = {"ur": ("ur-PK", "ur-PK-UzmaNeural"), "en": ("en-IN", "en-IN-NeerjaNeural")}
# ur-PK returns HTTP 400 on the short-audio REST API (tested live 2026-11-21, uaenorth); ur-IN works.
STT_LANGUAGES = {"ur": "ur-IN", "en": "en-IN"}
AUDIO_FORMAT = "audio-24khz-48kbitrate-mono-mp3"  # ~6 KB per second: fine on a weak connection
MAX_TTS_CHARS = 400
MAX_STT_BYTES = 1_000_000  # ~30 s of 16 kHz mono WAV; the short-audio API takes at most 60 s
MEMORY_CACHE_ITEMS = 256
STT_TYPES = {"audio/wav": "audio/wav; codecs=audio/pcm; samplerate=16000", "audio/ogg": "audio/ogg; codecs=opus"}
ALL_ROLES = tuple(Role)


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    lang: Literal["ur", "en"] = "ur"


class AudioCache:
    """Small LRU in memory, plus an optional disk folder that survives restarts."""

    def __init__(self, max_items: int = MEMORY_CACHE_ITEMS):
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._max = max_items
        self._lock = threading.Lock()

    def get(self, key: str, folder: str | None) -> bytes | None:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        path = Path(folder, f"{key}.mp3") if folder else None
        if path and path.is_file():
            data = path.read_bytes()
            self._put_memory(key, data)
            return data
        return None

    def put(self, key: str, data: bytes, folder: str | None) -> None:
        self._put_memory(key, data)
        if folder:
            try:
                Path(folder).mkdir(parents=True, exist_ok=True)
                Path(folder, f"{key}.mp3").write_bytes(data)
            except OSError as exc:  # disk cache is a nice-to-have; memory still works
                log.warning("TTS disk cache write failed: %s", type(exc).__name__)

    def _put_memory(self, key: str, data: bytes) -> None:
        with self._lock:
            self._items[key] = data
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


cache = AudioCache()
_transport: httpx.BaseTransport | None = None  # tests swap in an httpx.MockTransport


def cache_key(voice: str, text: str) -> str:
    return hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()


def _ssml(locale: str, voice: str, text: str) -> str:
    return (f"<speak version='1.0' xml:lang='{locale}'><voice xml:lang='{locale}' name='{voice}'>"
            f"{escape(text)}</voice></speak>")


def synthesise(settings: Settings, text: str, lang: str) -> bytes:
    locale, voice = VOICES[lang]
    url = f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key or "",
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": AUDIO_FORMAT,
        "User-Agent": "sahara-prototype",
    }
    with httpx.Client(timeout=settings.azure_timeout_seconds, transport=_transport) as client:
        response = client.post(url, content=_ssml(locale, voice, text).encode("utf-8"), headers=headers)
    response.raise_for_status()
    return response.content


def _not_configured() -> JSONResponse:
    return fail(code="TTS_NOT_CONFIGURED", message="Server speech is not set up; the app uses the phone's voice.", status=503)


@router.post("/tts", response_model=None)
@limiter.limit("60/minute")
def text_to_speech(request: Request, body: TtsIn, principal: Principal = Depends(require_roles(*ALL_ROLES))) -> Response:
    """Return MP3 audio for a short text. Cached, so repeated prompts cost nothing."""
    settings = get_settings()
    if not settings.speech_configured:
        return _not_configured()
    text = " ".join(body.text.split())
    _, voice = VOICES[body.lang]
    key = cache_key(voice, text)
    audio = cache.get(key, settings.tts_cache_dir)
    hit = audio is not None
    if audio is None:
        try:
            audio = synthesise(settings, text, body.lang)
        except httpx.HTTPError as exc:
            log.warning("Azure TTS failed: %s", type(exc).__name__)  # never the key or the text
            return fail(code="TTS_UNAVAILABLE", message="Speech is not available right now.", status=503)
        cache.put(key, audio, settings.tts_cache_dir)
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "private, max-age=86400", "X-Cache": "hit" if hit else "miss", "ETag": f'"{key[:32]}"'})


def recognise(settings: Settings, data: bytes, content_type: str, language: str) -> dict:
    url = (f"https://{settings.azure_speech_region}.stt.speech.microsoft.com/speech/recognition/conversation/"
           f"cognitiveservices/v1?language={language}&format=detailed")
    headers = {"Ocp-Apim-Subscription-Key": settings.azure_speech_key or "", "Content-Type": content_type, "Accept": "application/json"}
    with httpx.Client(timeout=settings.azure_timeout_seconds, transport=_transport) as client:
        response = client.post(url, content=data, headers=headers)
    response.raise_for_status()
    return response.json()


@router.post("/stt", response_model=None)
@limiter.limit("20/minute")
def speech_to_text(
    request: Request, audio: UploadFile = File(...), lang: Literal["ur", "en"] = Query("ur"),
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
) -> Response | dict:
    """Short audio (16 kHz mono WAV or Ogg/Opus, <= ~30 s) to text in ur-IN Urdu. Pre-fill only: the user confirms."""
    settings = get_settings()
    if not settings.speech_configured:
        return fail(code="STT_NOT_CONFIGURED", message="Server speech input is not set up.", status=503)
    kind = (audio.content_type or "").split(";")[0].strip().lower()
    if kind not in STT_TYPES:
        return fail(code="UNSUPPORTED_AUDIO", message="Send 16 kHz mono WAV or Ogg/Opus audio.", status=415)
    data = audio.file.read(MAX_STT_BYTES + 1)
    if not data or len(data) > MAX_STT_BYTES:
        return fail(code="AUDIO_TOO_LONG", message="Please record a shorter answer (about 30 seconds at most).", status=413)
    try:
        result = recognise(settings, data, STT_TYPES[kind], STT_LANGUAGES[lang])
    except httpx.HTTPError as exc:
        log.warning("Azure STT failed: %s", type(exc).__name__)
        return fail(code="STT_UNAVAILABLE", message="Speech input is not available right now.", status=503)
    best = (result.get("NBest") or [{}])[0]
    return ok({
        "status": result.get("RecognitionStatus"), "text": result.get("DisplayText", ""),
        "confidence": best.get("Confidence"), "language": STT_LANGUAGES[lang], "prefill_only": True,
    })
