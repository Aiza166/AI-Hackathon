"""Judge console API: platform-admin only, audited, no secrets, AI outage simulation with auto-expiry."""
import httpx
import pytest
from PIL import Image

from app.ai.second_sensor import SecondSensor
from app.api import judge, speech
from app.core import outages
from app.core.config import Settings
from app.decision.jev_client import JevClient, JevUnavailable
from app.documents import ocr
from app.evaluation import runner
from app.models.audit import AuditEvent

STAFF_ENDPOINTS = [
    ("get", "/api/v1/admin/judge/status", None),
    ("get", "/api/v1/admin/judge/activity", None),
    ("post", "/api/v1/admin/judge/outages", {"target": "jev", "down": True}),
    ("get", "/api/v1/admin/judge/sample-docs", None),
    ("get", "/api/v1/admin/judge/sample-docs/death_certificate_aslam_edited.png", None),
]
# Sentinel values (not real secrets), built at runtime: none of them may appear in any console response.
SECRET_FIELDS = ("typesafe_api_key", "second_sensor_key", "second_sensor_endpoint", "azure_docintel_key",
                 "azure_docintel_endpoint", "azure_speech_key")
SECRETS = {name: f"sentinel-{index}-{name.replace('_', '-')}" for index, name in enumerate(SECRET_FIELDS)}


def _latest(db, action: str) -> AuditEvent | None:
    return db.query(AuditEvent).filter(AuditEvent.action == action).order_by(AuditEvent.seq.desc()).first()


def _configured(**over) -> Settings:
    return Settings(jwt_secret="x" * 40, second_sensor_deployment="gpt-5-mini", azure_speech_region="uaenorth",
                    second_sensor_api_version="2025-04-01-preview", **{**SECRETS, **over})


@pytest.mark.parametrize("who", ["zainab", "helper", "officer", "auditor"])
@pytest.mark.parametrize(("method", "path", "body"), STAFF_ENDPOINTS)
def test_only_the_platform_admin_can_use_the_console(client, login, db, who, method, path, body):
    headers = login(who)
    response = client.request(method.upper(), path, json=body, headers=headers)
    assert response.status_code == 403
    event = _latest(db, "ACCESS_DENIED")
    assert event is not None and path in event.resource
    assert not outages.is_down("jev")


def test_console_needs_a_sign_in(client):
    assert client.get("/api/v1/admin/judge/status").status_code == 401


def test_status_reports_booleans_and_model_ids_never_secrets(client, login, db, monkeypatch):
    monkeypatch.setattr(judge, "get_settings", _configured)
    response = client.get("/api/v1/admin/judge/status", headers=login("admin"))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    for secret in SECRETS.values():
        assert secret not in response.text
    providers = data["providers"]
    assert providers["jev"] is True and providers["second_sensor"] is True
    assert providers["azure_ocr"] is True and providers["azure_speech"] is True
    assert providers["second_sensor_model"] == "gpt-5-mini" and providers["jev_model"] == "jev-1.14.0"
    assert data["readiness"]["database"] == "ok"
    assert set(data["faults"]) == {"identity", "frc", "death_registry", "pension_office", "payments", "raast"}
    assert data["audit_chain"]["intact"] is True
    assert set(data["outages"]) == set(outages.TARGETS)
    assert data["last_eval"]["generated_at"]
    assert _latest(db, "JUDGE_CONSOLE_STATUS_READ").role == "admin"


def test_unconfigured_providers_report_false(client, login):
    data = client.get("/api/v1/admin/judge/status", headers=login("admin")).json()["data"]
    assert data["providers"]["jev"] is False and data["providers"]["second_sensor_model"] is None
    assert data["readiness"]["jev_reachable"] is False


def test_jev_outage_is_audited_raises_jev_unavailable_and_can_be_restored(client, login, db):
    headers = login("admin")
    response = client.post("/api/v1/admin/judge/outages", json={"target": "jev", "down": True}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["expires_at"]
    event = _latest(db, "AI_OUTAGE_SIMULATED")
    assert event.details["target"] == "jev" and event.details["down"] is True and event.role == "admin"

    calls = []
    jev = JevClient(_configured(), transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200, json={})))
    with pytest.raises(JevUnavailable, match="simulated"):
        jev.ask("state", {"q": {"type": "noul", "instructions": "x"}})
    assert jev.reachable() is False and calls == []  # nothing left the server
    status = client.get("/api/v1/admin/judge/status", headers=headers).json()["data"]
    assert status["outages"]["jev"]["simulated_down"] is True and status["readiness"]["jev_simulated_down"] is True

    client.post("/api/v1/admin/judge/outages", json={"target": "jev", "down": False}, headers=headers)
    assert not outages.is_down("jev")
    assert _latest(db, "AI_OUTAGE_SIMULATED").details["down"] is False


def test_outage_switches_off_by_itself():
    outages.set_outage("jev", True, minutes=-1)  # already past its 15-minute expiry
    assert not outages.is_down("jev")
    assert outages.status()["jev"] == {"simulated_down": False, "expires_at": None}


def test_unknown_outage_target_is_rejected(client, login):
    response = client.post("/api/v1/admin/judge/outages", json={"target": "openai_key", "down": True}, headers=login("admin"))
    assert response.status_code == 422


def test_second_sensor_outage_returns_unavailable_without_a_call():
    outages.set_outage("second_sensor", True)
    calls = []
    sensor = SecondSensor(_configured(), transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500)))
    answers = sensor.ask({"asks_fee": "Does it ask for a fee?"}, untrusted_text="pay 500")
    assert answers.status == "unavailable" and calls == []


def test_azure_ocr_outage_skips_azure_and_falls_back(monkeypatch):
    outages.set_outage("azure_ocr", True)
    calls = []
    fallback = ocr.OcrResult(engine="tesseract", lines=[])
    monkeypatch.setattr(ocr.TesseractEngine, "read", lambda self, img: fallback)
    result = ocr.run_ocr(Image.new("RGB", (400, 300), "white"), _configured(),
                         transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500)))
    assert result is fallback and calls == []


def test_azure_speech_outage_fails_like_an_azure_error(client, login, monkeypatch):
    outages.set_outage("azure_speech", True)
    with pytest.raises(httpx.HTTPError):
        speech.recognise(_configured(), b"RIFF", "audio/wav", "ur-IN")
    monkeypatch.setattr(speech, "get_settings", _configured)
    response = client.post("/api/v1/speech/tts", json={"text": "Salam", "lang": "ur"}, headers=login("zainab"))
    assert response.status_code == 503 and response.json()["error"]["code"] == "TTS_UNAVAILABLE"


def test_frc_fault_routes_a_claim_to_an_officer(client, login, file_claim):
    response = client.post("/api/v1/admin/faults", json={"service": "frc", "mode": "timeout"}, headers=login("admin"))
    assert response.status_code == 200, response.text
    body = file_claim("zainab")
    decision = body["data"]["latest_decision"]
    assert body["data"]["status"] == "in_review"
    assert "SERVICE_UNAVAILABLE" in decision["reason_codes"]


def test_activity_feed_has_no_ids_or_details_and_logs_reads_sparingly(client, login, db):
    headers = login("admin")
    first = client.get("/api/v1/admin/judge/activity", headers=headers)
    assert first.status_code == 200, first.text
    rows = first.json()["data"]
    assert 0 < len(rows) <= 20
    assert set(rows[0]) == {"seq", "ts", "actor_type", "role", "action", "reason"}
    reads_before = db.query(AuditEvent).filter(AuditEvent.action == "AUDIT_READ", AuditEvent.resource == "judge_console").count()
    client.get("/api/v1/admin/judge/activity", headers=headers)
    reads_after = db.query(AuditEvent).filter(AuditEvent.action == "AUDIT_READ", AuditEvent.resource == "judge_console").count()
    assert reads_after == reads_before  # polling every 10 s does not flood the audit log


def test_activity_reason_shows_route_and_reason_codes(client, login, file_claim):
    client.post("/api/v1/admin/faults", json={"service": "identity", "mode": "error"}, headers=login("admin"))
    file_claim("zainab")
    rows = client.get("/api/v1/admin/judge/activity", headers=login("admin")).json()["data"]
    reasons = [r["reason"] or "" for r in rows]
    assert any("SERVICE_UNAVAILABLE" in r for r in reasons)
    assert any(r == "identity: error" for r in reasons)
    assert not any("9000000000022" in r for r in reasons)


def test_sample_docs_list_and_download_are_allowlisted_and_audited(client, login, db):
    headers = login("admin")
    listing = client.get("/api/v1/admin/judge/sample-docs", headers=headers).json()["data"]
    names = {d["file"] for d in listing}
    assert "death_certificate_aslam_edited.png" in names and len(names) == 20
    assert sum(d["edited"] for d in listing) == 2
    response = client.get("/api/v1/admin/judge/sample-docs/death_certificate_aslam_edited.png", headers=headers)
    assert response.status_code == 200 and response.content[:4] == b"\x89PNG"
    assert response.headers["content-type"] == "image/png"
    assert _latest(db, "SAMPLE_DOC_DOWNLOADED").details["edited"] is True
    for bad in ("manifest.json", "..%2F..%2Fapp%2Fcore%2Fconfig.py", "..%5Cmanifest.json", "nope.png"):
        assert client.get(f"/api/v1/admin/judge/sample-docs/{bad}", headers=headers).status_code == 404


def test_demo_reset_ends_simulated_outages(client, login):
    headers = login("admin")
    client.post("/api/v1/admin/judge/outages", json={"target": "second_sensor", "down": True}, headers=headers)
    assert outages.is_down("second_sensor")
    assert client.post("/api/v1/admin/seed/reset", headers=headers).status_code == 200
    assert not outages.is_down("second_sensor")


def test_offline_eval_rerun_keeps_the_last_live_tiers_for_comparison():
    result = runner.run_all()
    assert result["scam"]["tiers"]["jev_only"]["status"] == "not_run"
    reference = result["reference_live"]
    assert reference is not None and reference["generated_at"]
    assert reference["scam_tiers"]["cascade"]["status"] == "ran"
    assert "items" not in reference["scam_tiers"]["cascade"]
    deterministic = result["documents"]["tiers"]["deterministic"]
    assert {"p95_latency_ms", "cost_per_check_usd", "models"} <= set(deterministic)
    assert deterministic["models"] == []
