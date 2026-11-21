"""Speech endpoints: Azure TTS/STT mocked with httpx.MockTransport; cache; 503 when not configured."""
import httpx
import pytest

from app.api import speech
from app.core.config import get_settings


@pytest.fixture
def azure(monkeypatch, tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-speech-key"
        if "tts.speech" in request.url.host:
            return httpx.Response(200, content=b"ID3" + b"\x00" * 2000, headers={"Content-Type": "audio/mpeg"})
        return httpx.Response(200, json={"RecognitionStatus": "Success", "DisplayText": "محمد اسلم",
                                         "NBest": [{"Confidence": 0.91}]})

    settings = get_settings().model_copy(update={
        "azure_speech_key": "test-speech-key", "azure_speech_region": "uaenorth", "tts_cache_dir": str(tmp_path)})
    monkeypatch.setattr(speech, "get_settings", lambda: settings)
    monkeypatch.setattr(speech, "_transport", httpx.MockTransport(handler))
    speech.cache.clear()
    yield calls
    speech.cache.clear()


def test_tts_not_configured_is_a_clear_503(client, login):
    response = client.post("/api/v1/speech/tts", json={"text": "سلام", "lang": "ur"}, headers=login("zainab"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TTS_NOT_CONFIGURED"


def test_tts_needs_a_signed_in_user_and_short_text(client, login):
    assert client.post("/api/v1/speech/tts", json={"text": "سلام"}).status_code == 401
    too_long = client.post("/api/v1/speech/tts", json={"text": "a" * (speech.MAX_TTS_CHARS + 1)}, headers=login("zainab"))
    assert too_long.status_code == 422
    assert client.post("/api/v1/speech/tts", json={"text": "hi", "lang": "fr"}, headers=login("zainab")).status_code == 422


def test_tts_returns_mp3_with_the_urdu_voice_and_caches_it(client, login, azure, tmp_path):
    headers = login("zainab")
    first = client.post("/api/v1/speech/tts", json={"text": "آپ کا دعویٰ محفوظ ہے", "lang": "ur"}, headers=headers)
    assert first.status_code == 200 and first.headers["content-type"] == "audio/mpeg"
    assert first.headers["x-cache"] == "miss" and len(first.content) > 1000
    ssml = azure[0].content.decode("utf-8")
    assert "ur-PK-UzmaNeural" in ssml and azure[0].headers["X-Microsoft-OutputFormat"].endswith("mp3")
    second = client.post("/api/v1/speech/tts", json={"text": "آپ کا دعویٰ  محفوظ ہے", "lang": "ur"}, headers=headers)
    assert second.headers["x-cache"] == "hit" and second.content == first.content
    assert len(azure) == 1  # synthesised once
    assert len(list(tmp_path.glob("*.mp3"))) == 1  # and kept on disk for restarts


def test_tts_escapes_text_into_ssml(client, login, azure):
    client.post("/api/v1/speech/tts", json={"text": "<break/> & </voice>", "lang": "en"}, headers=login("zainab"))
    ssml = azure[0].content.decode("utf-8")
    assert "&lt;break/&gt; &amp; &lt;/voice&gt;" in ssml and "en-IN-NeerjaNeural" in ssml


def test_tts_upstream_error_is_a_503_without_details(client, login, monkeypatch, azure):
    monkeypatch.setattr(speech, "_transport", httpx.MockTransport(lambda r: httpx.Response(401, text="bad key xyz")))
    response = client.post("/api/v1/speech/tts", json={"text": "hello", "lang": "en"}, headers=login("zainab"))
    assert response.status_code == 503 and response.json()["error"]["code"] == "TTS_UNAVAILABLE"
    assert "xyz" not in response.text


def test_stt_prefills_text_and_checks_audio_type(client, login, azure):
    headers = login("zainab")
    ok = client.post("/api/v1/speech/stt?lang=ur", files={"audio": ("a.wav", b"RIFF" + b"\x00" * 100, "audio/wav")}, headers=headers)
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["text"] == "محمد اسلم" and data["prefill_only"] and data["language"] == "ur-IN"
    assert "language=ur-IN" in str(azure[0].url)
    bad = client.post("/api/v1/speech/stt", files={"audio": ("a.webm", b"x", "audio/webm")}, headers=headers)
    assert bad.status_code == 415
