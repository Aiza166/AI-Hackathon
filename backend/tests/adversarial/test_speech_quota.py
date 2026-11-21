"""L2: per-user limits on uncached TTS synthesis; cached clips are unaffected; free text is short."""
import httpx
import pytest

from app.api import speech
from app.core.config import get_settings


@pytest.fixture
def azure(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=b"ID3" + b"\x00" * 100, headers={"Content-Type": "audio/mpeg"})

    settings = get_settings().model_copy(update={"azure_speech_key": "k", "azure_speech_region": "uaenorth", "tts_cache_dir": None})
    monkeypatch.setattr(speech, "get_settings", lambda: settings)
    monkeypatch.setattr(speech, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(speech, "synth_minute", speech.PerUserQuota(3, 60))
    speech.cache.clear()
    yield calls
    speech.cache.clear()


def test_uncached_synthesis_is_limited_per_user_but_cache_hits_are_not(client, login, azure):
    zainab = login("zainab")
    codes = [client.post("/api/v1/speech/tts", json={"text": f"line {i}", "lang": "en"}, headers=zainab).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.post("/api/v1/speech/tts", json={"text": "line 0", "lang": "en"}, headers=zainab).status_code == 200  # cached
    assert client.post("/api/v1/speech/tts", json={"text": "other user", "lang": "en"}, headers=login("rukhsana")).status_code == 200
    assert len(azure) == 4


def test_free_text_length_is_restricted(client, login):
    assert speech.MAX_TTS_CHARS <= 200
    assert client.post("/api/v1/speech/tts", json={"text": "a" * 201}, headers=login("zainab")).status_code == 422
