"""Scam Shield v2 API: links, calls, screenshot (OCR) and voice note (STT) intake, the second-sensor
cascade, officer-only advisory note, and what is recorded per check."""
import io
import math
import shutil
import struct
import wave

import httpx
import pytest
from PIL import Image

from app.ai.second_sensor import SecondSensor, SensorAnswers
from app.api import speech
from app.core.config import get_settings
from app.decision.jev_client import JevResult
from app.documents.ocr import OcrLine, OcrResult, OcrUnavailable
from app.models.audit import AuditEvent
from app.models.scam import ScamCheck
from app.scam import audio, screenshot


def _jev(monkeypatch, probabilities: dict[str, float]):
    def ask(self, state, questions):
        return JevResult(model="jev-1.14.0", answers={k: {"noul": probabilities.get(k, 0.02)} for k in questions}, latency_ms=7,
                         usage={"input_tokens": 500})
    monkeypatch.setattr("app.decision.jev_client.JevClient.ask", ask)


def _second(monkeypatch, probabilities: dict[str, float], note="AI-written, advisory: Asks to pay a fee."):
    calls = []

    def ask(self, questions, untrusted_text=None, image_jpeg=None):
        calls.append(untrusted_text)
        return SensorAnswers(status="ok", model="gpt-4o-mini", probabilities={q: probabilities.get(q, 0.05) for q in questions},
                             note=note, latency_ms=300, cost_usd=0.00007, used_logprobs=True)
    monkeypatch.setattr(SecondSensor, "configured", property(lambda self: True))
    monkeypatch.setattr(SecondSensor, "ask", ask)
    return calls


def _post(client, headers, **body):
    response = client.post("/api/v1/scam/check", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_lookalike_link_alone_is_likely_scam_and_link_findings_are_returned(client, login, monkeypatch):
    _jev(monkeypatch, {"has_link": 0.97, "claims_government": 0.9})
    data = _post(client, login("zainab"), text="Apni BISP raqam ke liye https://bisp-gov.pk.claim-now.xyz/login kholen")
    assert data["verdict"] == "LIKELY_SCAM"
    assert any("imitates an official website" in r for r in data["reasons"])
    assert data["links"][0]["findings"] and data["links"][0]["fetched"] is False


def test_official_link_with_genuine_text_can_look_genuine(client, login, monkeypatch):
    _jev(monkeypatch, {"has_link": 0.95, "claims_government": 0.9})
    data = _post(client, login("zainab"), text="Your claim status is on https://pension.gov.example/status. No fee is charged.",
                 sender="PENSION-GOV")
    assert data["verdict"] == "LOOKS_GENUINE"


def test_call_from_official_short_code_is_flagged_with_spoof_reason(client, login, monkeypatch):
    _jev(monkeypatch, {"asks_secret": 0.5, "claims_government": 0.95})
    data = _post(client, login("zainab"), text="Caller said he is from BISP and needs the code sent to my phone.",
                 sender="8171", channel="call", on_call_with_unknown=True)
    assert any("do not call you" in r for r in data["reasons"])
    assert data["verdict"] in ("LIKELY_SCAM", "NOT_SURE")


def test_cascade_runs_second_sensor_only_when_jev_is_undecided(client, login, monkeypatch):
    _jev(monkeypatch, {"asks_fee": 0.98})
    calls = _second(monkeypatch, {"asks_fee": 0.98})
    _post(client, login("zainab"), text="Pay Rs 500 fee to release your pension.")
    assert calls == []  # Jev was clear: no second opinion needed
    _jev(monkeypatch, {"asks_fee": 0.5})
    data = _post(client, login("zainab"), text="Pay Rs 500 fee to release your pension.")
    assert len(calls) == 1 and data["verdict"] == "LIKELY_SCAM"  # resolved by the second sensor


def test_sensor_disagreement_is_not_sure(client, login, monkeypatch):
    _jev(monkeypatch, {"asks_fee": 0.05})  # Jev: no fee; keyword rule: "fee" present
    _second(monkeypatch, {"asks_fee": 0.95})  # second sensor sides with the rule
    data = _post(client, login("zainab"), text="Send the fee to the agent today.")
    assert data["verdict"] == "NOT_SURE"
    assert any("did not agree" in r for r in data["reasons"])


def test_officer_gets_advisory_note_and_sensors_citizen_does_not(client, login, monkeypatch):
    _jev(monkeypatch, {"asks_fee": 0.5})
    _second(monkeypatch, {"asks_fee": 0.95})
    citizen = _post(client, login("zainab"), text="Pay the fee now.")
    officer = _post(client, login("officer"), text="Pay the fee now.")
    assert "officer_note" not in citizen and "sensors" not in citizen
    assert officer["officer_note"].startswith("AI-written, advisory")
    assert {s["name"] for s in officer["sensors"]} == {"deterministic", "jev", "second_sensor"}


def test_sensors_latency_and_cost_recorded_in_signals_and_audit(client, login, monkeypatch, db):
    _jev(monkeypatch, {"asks_fee": 0.5})
    _second(monkeypatch, {"asks_fee": 0.95})
    _post(client, login("zainab"), text="Pay the fee now.")
    stored = db.query(ScamCheck).one()
    assert [s["name"] for s in stored.signals["sensors"]] == ["deterministic", "jev", "second_sensor"]
    assert stored.signals["cost_usd"] > 0 and "latency_ms" in stored.signals
    event = db.query(AuditEvent).filter(AuditEvent.action == "SCAM_CHECKED").order_by(AuditEvent.seq.desc()).first()
    assert event.details["sensors"][2]["status"] == "ok" and event.details["cost_usd"] > 0
    assert "Pay the fee" not in str(event.details)  # never the message text


def test_second_sensor_disabled_cleanly_without_env(client, login, monkeypatch):
    _jev(monkeypatch, {"asks_fee": 0.5})
    data = _post(client, login("officer"), text="Pay the fee now.")
    assert [s["name"] for s in data["sensors"]] == ["deterministic", "jev"]
    assert data["officer_note"] == ""


# ---- screenshot --------------------------------------------------------------------------------

def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 700), "white").save(buf, "PNG")
    return buf.getvalue()


def _fake_ocr(monkeypatch, lines: list[str]):
    result = OcrResult(engine="tesseract", lines=[OcrLine(t, 0.9, (0, i * 20, 300, i * 20 + 18)) for i, t in enumerate(lines)])
    monkeypatch.setattr("app.api.scam.run_ocr", lambda img: result)


def test_screenshot_is_read_and_sender_number_parsed(client, login, monkeypatch, db):
    _jev(monkeypatch, {"asks_fee": 0.97, "claims_government": 0.9})
    _fake_ocr(monkeypatch, ["10:42", "+92 300 0000001", "online", "Mubarak! Aap ki pension release ho gayi.",
                            "Rs 3000 fee jama karwain", "11:02 AM"])
    response = client.post("/api/v1/scam/check-image", files={"file": ("chat.png", _png(), "image/png")},
                           data={"area": "Karachi East"}, headers=login("zainab"))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["verdict"] == "LIKELY_SCAM"
    assert data["extracted"]["sender_found"] is True
    assert "fee jama" in data["extracted"]["text"] and "10:42" not in data["extracted"]["text"]
    assert db.query(ScamCheck).one().signals["source"] == "screenshot"


def test_screenshot_rejects_non_images_and_handles_ocr_outage(client, login, monkeypatch):
    bad = client.post("/api/v1/scam/check-image", files={"file": ("a.txt", b"hello", "text/plain")}, headers=login("zainab"))
    assert bad.status_code == 415

    def down(img):
        raise OcrUnavailable("no engine")
    monkeypatch.setattr("app.api.scam.run_ocr", down)
    response = client.post("/api/v1/scam/check-image", files={"file": ("c.png", _png(), "image/png")}, headers=login("zainab"))
    assert response.status_code == 503 and response.json()["error"]["code"] == "OCR_UNAVAILABLE"


def test_chat_text_parser_drops_status_lines():
    text, sender = screenshot.chat_text(OcrResult("t", [OcrLine(t, 0.9, (0, 0, 1, 1)) for t in
                                                        ["9:41", "4G 85%", "0300-0000002", "typing...", "Send OTP now", "Today"]]))
    assert text == "0300-0000002\nSend OTP now" and sender == "0300-0000002"


# ---- voice note / call recording -----------------------------------------------------------------

def _wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 8))) for i in range(int(seconds * rate))))
    return buf.getvalue()


@pytest.fixture
def stt(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"RecognitionStatus": "Success", "DisplayText": "Aap apna code bata dein, main BISP se bol raha hoon",
                                         "NBest": [{"Confidence": 0.8}]})
    settings = get_settings().model_copy(update={"azure_speech_key": "test-speech-key", "azure_speech_region": "uaenorth"})
    monkeypatch.setattr(speech, "get_settings", lambda: settings)
    monkeypatch.setattr(speech, "_transport", httpx.MockTransport(handler))
    return seen


def test_voice_note_not_configured_is_503(client, login):
    response = client.post("/api/v1/scam/check-audio", files={"audio": ("v.wav", _wav(), "audio/wav")}, headers=login("zainab"))
    assert response.status_code == 503 and response.json()["error"]["code"] == "STT_NOT_CONFIGURED"


def test_voice_note_is_transcribed_and_checked_as_a_call(client, login, monkeypatch, stt, db):
    _jev(monkeypatch, {"asks_secret": 0.96, "claims_government": 0.9})
    response = client.post("/api/v1/scam/check-audio", files={"audio": ("v.wav", _wav(), "audio/wav")},
                           data={"kind": "call_recording", "lang": "ur"}, headers=login("zainab"))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["verdict"] == "LIKELY_SCAM" and "code bata" in data["extracted"]["text"]
    assert stt[0].headers["Content-Type"].startswith("audio/wav")
    stored = db.query(ScamCheck).one()
    assert stored.signals["channel"] == "call" and stored.signals["source"] == "call_recording"


def test_voice_note_rejects_other_files(client, login, stt):
    response = client.post("/api/v1/scam/check-audio", files={"audio": ("x.pdf", b"%PDF", "application/pdf")}, headers=login("zainab"))
    assert response.status_code == 415


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_ffmpeg_converts_to_16k_mono_wav_and_trims():
    out, kind = audio.prepare_for_stt(_wav(seconds=2.0, rate=44100), "audio/wav")
    assert kind == "audio/wav"
    with wave.open(io.BytesIO(out)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1


def test_without_ffmpeg_webm_is_unsupported_but_wav_passes(monkeypatch):
    monkeypatch.setattr(audio, "ffmpeg_path", lambda: None)
    with pytest.raises(audio.AudioUnsupported):
        audio.prepare_for_stt(b"\x1aE\xdf\xa3webm", "audio/webm")
    data, kind = audio.prepare_for_stt(_wav(), "audio/wav")
    assert kind == "audio/wav" and data.startswith(b"RIFF")


def test_ffmpeg_failure_is_unsupported(monkeypatch):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    with pytest.raises(audio.AudioUnsupported):
        audio.prepare_for_stt(b"not audio at all" * 10, "audio/webm")
