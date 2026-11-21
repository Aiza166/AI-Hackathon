"""Security hardening: headers, body/upload limits, revocable refresh tokens, IDOR, rate limits, PII redaction.

Each test maps to a row in docs/SECURITY-CHECKLIST.md.
"""
import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit import AuditEvent
from tests.conftest import BASE_CLAIM, PHONES
from tests.doc_fixtures import sample

ZAINAB_CNIC = BASE_CLAIM["claimant_cnic"]


@pytest.fixture
def proxy_hops():
    """Pretend one proxy (Railway) sits in front of the API for this test."""
    settings = get_settings()
    before = settings.rate_limit_proxy_hops
    settings.rate_limit_proxy_hops = 1
    yield
    settings.rate_limit_proxy_hops = before


def _upload(client, headers, case_id, data, content_type="image/png", kind="death_certificate"):
    return client.post(f"/api/v1/cases/{case_id}/documents", data={"kind": kind},
                       files={"file": ("photo", data, content_type)}, headers=headers)


def _png(size: tuple[int, int], mode: str = "L") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- security headers

def test_api_responses_carry_security_headers(client):
    response = client.get("/healthz")
    h = response.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert h["strict-transport-security"].startswith("max-age=31536000")
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert "default-src 'none'" in h["content-security-policy"]
    assert "camera=()" in h["permissions-policy"] and "microphone=()" in h["permissions-policy"]
    assert h["cache-control"] == "no-store"


def test_error_responses_also_carry_headers(client):
    response = client.get("/api/v1/cases")  # 401
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_swagger_docs_get_a_csp_that_lets_them_load(client):
    csp = client.get("/docs").headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp and "frame-ancestors 'none'" in csp


def test_cors_does_not_allow_credentials(client):
    response = client.options("/api/v1/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers
    evil = client.options("/api/v1/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers


# ---------------------------------------------------------------- body size and uploads

def test_oversized_body_is_refused_before_parsing(client, login):
    headers = login("zainab")
    response = client.post("/api/v1/cases", content=b"x" * (10 * 1024 * 1024),
                           headers={**headers, "Content-Type": "application/json", "Origin": "http://localhost:5173"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    # The browser can read the 413 (CORS) and it carries the security headers.
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_chunked_body_over_the_cap_is_refused(client, login):
    headers = login("zainab")

    def chunks():
        for _ in range(10):
            yield b"x" * (1024 * 1024)

    response = client.post("/api/v1/cases", content=chunks(), headers={**headers, "Content-Type": "application/json"})
    assert response.status_code == 413


def test_upload_rejects_wrong_magic_bytes_even_with_image_type(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    headers = login("zainab")
    for fake in (b"<?php echo 1; ?>", b"%PDF-1.7 ....", b"GIF89a" + b"\x00" * 50, b"<svg xmlns='http://www.w3.org/2000/svg'/>"):
        assert _upload(client, headers, case_id, fake, "image/jpeg").status_code == 415


def test_upload_rejects_png_bytes_declared_as_jpeg_inside_pillow(monkeypatch):
    from app.documents.imaging import BadImage, load

    # Magic says PNG but the data is really a GIF after the first bytes: Pillow and the sniff disagree.
    with pytest.raises(BadImage):
        load(b"\x89PNG\r\n\x1a\n" + b"garbage" * 10)


def test_upload_over_8_mb_is_refused(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    big = b"\xff\xd8\xff" + b"\x00" * (8 * 1024 * 1024)
    assert _upload(client, login("zainab"), case_id, big, "image/jpeg").status_code == 413


def test_decompression_bomb_is_refused(client, login, file_claim):
    # 7000 x 6000 = 42 M pixels in a tiny PNG: between 1x and 2x Pillow's limit, where Pillow only warns.
    bomb = _png((7000, 6000))
    assert len(bomb) < 1024 * 1024
    case_id = file_claim("zainab")["data"]["id"]
    response = _upload(client, login("zainab"), case_id, bomb)
    assert response.status_code == 422
    assert "pixels" in response.json()["error"]["message"]


def test_pillow_pixel_limit_is_set_at_import():
    import app.documents.imaging as imaging

    assert Image.MAX_IMAGE_PIXELS == imaging.MAX_PIXELS


def test_stored_copy_has_no_exif():
    from app.documents.imaging import jpeg_bytes, load

    exif = Image.Exif()
    exif[0x010F] = "MockCam"  # Make
    exif[0x0131] = "MockEditor"  # Software
    src = Image.open(io.BytesIO(sample("death_certificate_aslam.whatsapp.jpg"))).convert("RGB")
    buf = io.BytesIO()
    src.save(buf, "JPEG", exif=exif.tobytes())
    loaded = load(buf.getvalue())
    assert loaded.exif.get("camera_make") == "MockCam"  # read once as officer context
    stored = Image.open(io.BytesIO(jpeg_bytes(loaded.image)))
    assert len(stored.getexif()) == 0
    assert "exif" not in stored.info


def test_stt_rejects_audio_whose_bytes_do_not_match_the_type(client, login, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "azure_speech_key", "k")
    monkeypatch.setattr(settings, "azure_speech_region", "r")
    response = client.post("/api/v1/speech/stt", files={"audio": ("a.wav", b"MZ\x90\x00" + b"\x00" * 50, "audio/wav")},
                           headers=login("zainab"))
    assert response.status_code == 415


# ---------------------------------------------------------------- refresh tokens: rotation and revocation

def _login_tokens(client, who="zainab") -> dict:
    return client.post("/api/v1/auth/login", json={"phone": PHONES[who], "pin": "1234"}).json()["data"]


def test_refresh_rotates_and_the_old_token_is_spent(client):
    tokens = _login_tokens(client)
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new = first.json()["data"]
    assert new["refresh_token"] != tokens["refresh_token"]
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 200


def test_reusing_a_refresh_token_ends_the_whole_session(client, db):
    tokens = _login_tokens(client)
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()["data"]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    # The legitimate holder's newer tokens die too: the session is revoked.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {rotated['access_token']}"}).status_code == 401
    actions = db.execute(select(AuditEvent.action).where(AuditEvent.action == "REFRESH_TOKEN_REUSED")).scalars().all()
    assert actions


def test_logout_revokes_refresh_and_access_tokens(client):
    tokens = _login_tokens(client)
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/v1/me", headers=auth).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_logout_of_one_session_keeps_other_sessions(client):
    phone_a, phone_b = _login_tokens(client), _login_tokens(client)
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {phone_a['access_token']}"})
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {phone_b['access_token']}"}).status_code == 200


def test_access_token_cannot_be_used_as_refresh_token(client):
    tokens = _login_tokens(client)
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401


def test_token_without_session_is_refused(client):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    from app.core.security import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER

    now = datetime.now(timezone.utc)
    forged = pyjwt.encode({"sub": "x", "typ": "access", "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "iat": now,
                           "exp": now + timedelta(minutes=5)}, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# ---------------------------------------------------------------- IDOR on every id route

def test_other_citizen_cannot_reach_any_route_of_a_case(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    rukhsana = login("rukhsana")
    for path in (f"/api/v1/cases/{case_id}", f"/api/v1/cases/{case_id}/explanation", f"/api/v1/cases/{case_id}/documents",
                 f"/api/v1/cases/{case_id}/documents/{uuid.uuid4()}", f"/api/v1/cases/{case_id}/payout-changes"):
        assert client.get(path, headers=rukhsana).status_code == 403, path
    assert _upload(client, rukhsana, case_id, sample("death_certificate_aslam.png")).status_code == 403
    assert client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000008"},
                       headers=rukhsana).status_code == 403
    assert client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "not mine"}, headers=rukhsana).status_code == 403


def test_document_id_of_a_hidden_case_does_not_leak_existence(client, login, file_claim):
    # A real document id and a made-up one look the same (403) to someone who cannot see the case.
    case_id = file_claim("zainab")["data"]["id"]
    doc = _upload(client, login("zainab"), case_id, sample("death_certificate_aslam.png")).json()["data"]
    rukhsana = login("rukhsana")
    real = client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}", headers=rukhsana)
    fake = client.get(f"/api/v1/cases/{case_id}/documents/{uuid.uuid4()}", headers=rukhsana)
    assert real.status_code == fake.status_code == 403
    for view in ("image", "ela"):
        assert client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}/{view}", headers=login("officer")).status_code == 200
        assert client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}/{view}", headers=login("welfare_officer")).status_code == 403


def test_document_of_another_case_is_not_found_through_my_case(client, login, file_claim):
    zainab_case = file_claim("zainab")["data"]["id"]
    doc = _upload(client, login("zainab"), zainab_case, sample("death_certificate_aslam.png")).json()["data"]
    rukhsana_case = file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", claimant_dob="1975-01-20",
                               deceased_cnic="9000000000044", deceased_name="Muhammad Aslam")["data"]["id"]
    response = client.get(f"/api/v1/cases/{rukhsana_case}/documents/{doc['id']}", headers=login("rukhsana"))
    assert response.status_code == 404


def test_payout_change_ids_are_guarded(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000008"},
                         headers=login("zainab")).json()["data"]
    rukhsana = login("rukhsana")
    # Right PIN for herself, but not her claim.
    assert client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=rukhsana).status_code == 403
    assert client.post(f"/api/v1/payout-changes/{change['id']}/cancel", headers=rukhsana).status_code == 403
    # An officer of another department cannot even learn the change exists.
    other = client.post(f"/api/v1/payout-changes/{change['id']}/approve", json={"note": "looks fine"}, headers=login("welfare_officer"))
    assert other.status_code == 404
    assert all(c["id"] != change["id"] for c in client.get("/api/v1/payout-changes?status=all", headers=login("welfare_officer")).json()["data"])


def test_speech_and_unknown_ids_need_auth_and_return_404(client, login):
    assert client.post("/api/v1/speech/tts", json={"text": "salam"}).status_code == 401
    assert client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=login("officer")).status_code == 404
    assert client.get(f"/api/v1/audit/cases/{uuid.uuid4()}/replay", headers=login("auditor")).status_code == 404


def test_withdrawn_consent_hides_cases_from_list_endpoints(client, login, file_claim):
    from tests.test_consent import _consent_id

    case_id = file_claim("zainab")["data"]["id"]
    zainab, helper, officer = login("zainab"), login("helper"), login("officer")
    assert any(c["id"] == case_id for c in client.get("/api/v1/cases", headers=helper).json()["data"])
    client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'helper')}/withdraw", headers=zainab)
    client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'department')}/withdraw", headers=zainab)
    assert all(c["id"] != case_id for c in client.get("/api/v1/cases", headers=helper).json()["data"])
    assert all(c["id"] != case_id for c in client.get("/api/v1/cases", headers=officer).json()["data"])
    assert any(c["id"] == case_id for c in client.get("/api/v1/cases", headers=login("auditor")).json()["data"])


def test_helper_cannot_probe_whether_a_cnic_exists(client, login):
    helper = login("helper")
    unassigned = client.post("/api/v1/cases", json={**BASE_CLAIM, "claimant_cnic": "9000000000033"}, headers=helper)
    unknown = client.post("/api/v1/cases", json={**BASE_CLAIM, "claimant_cnic": "9000099999999"}, headers=helper)
    assert unassigned.status_code == unknown.status_code == 403
    assert unassigned.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_case_close_cannot_overturn_a_decision(client, login, file_claim):
    approved = file_claim("zainab")["data"]
    assert approved["status"] == "auto_approved"
    assert client.post(f"/api/v1/cases/{approved['id']}/close", json={"reason": "tidy up"}, headers=login("admin")).status_code == 409


def test_only_an_officer_can_close_a_case_waiting_for_a_decision(client, login, file_claim):
    case_id = file_claim("zainab", claimant_dob=None)["data"]["id"]
    client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "please check"}, headers=login("zainab"))
    assert client.get(f"/api/v1/cases/{case_id}", headers=login("officer")).json()["data"]["status"] in ("in_review", "proof_requested")
    assert client.post(f"/api/v1/cases/{case_id}/close", json={"reason": "tidy up"}, headers=login("admin")).status_code == 403
    assert client.post(f"/api/v1/cases/{case_id}/close", json={"reason": "duplicate filing"}, headers=login("officer")).status_code == 200


# ---------------------------------------------------------------- rate limits and PIN lockout

def test_login_rate_limit_returns_429(client):
    statuses = [client.post("/api/v1/auth/login", json={"phone": "99999999999", "pin": "0000"}).status_code for _ in range(11)]
    assert statuses[-1] == 429
    assert statuses[0] == 401


def test_default_limit_covers_routes_without_their_own(client):
    statuses = [client.get("/healthz").status_code for _ in range(301)]
    assert statuses[:300].count(200) == 300
    assert statuses[300] == 429


def test_spoofed_forwarded_for_does_not_reset_the_limit(client, proxy_hops):
    # The caller controls the left part of X-Forwarded-For; Railway appends the real address on the right.
    statuses = [client.post("/api/v1/auth/login", json={"phone": "99999999999", "pin": "0000"},
                            headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code for i in range(11)]
    assert statuses[-1] == 429


def test_client_ip_uses_rightmost_hop(proxy_hops):
    from starlette.requests import Request

    from app.core.ratelimit import client_ip

    scope = {"type": "http", "headers": [(b"x-forwarded-for", b"1.2.3.4, 198.51.100.9")], "client": ("10.0.0.1", 1)}
    assert client_ip(Request(scope)) == "198.51.100.9"


def test_payout_pin_step_up_locks_after_5_wrong_pins(client, login, file_claim, proxy_hops):
    case_id = file_claim("zainab")["data"]["id"]
    zainab = login("zainab")
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000008"}, headers=zainab).json()["data"]
    url = f"/api/v1/payout-changes/{change['id']}/confirm"
    for i in range(5):  # a new address each time: the per-IP limit alone would not stop this
        assert client.post(url, json={"pin": "9999"}, headers={**zainab, "X-Forwarded-For": f"203.0.113.{i}"}).status_code == 401
    locked = client.post(url, json={"pin": "1234"}, headers={**zainab, "X-Forwarded-For": "203.0.113.99"})
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] != "RATE_LIMITED"  # the account lockout, not the IP limit


def test_wrong_login_pins_do_not_lock_the_payout_step_up(client, login, file_claim, proxy_hops):
    # Anyone who knows her phone number can fail her login; that must not block her payout confirm.
    case_id = file_claim("zainab")["data"]["id"]
    zainab = login("zainab")
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000008"}, headers=zainab).json()["data"]
    for i in range(5):
        client.post("/api/v1/auth/login", json={"phone": PHONES["zainab"], "pin": "9999"}, headers={"X-Forwarded-For": f"198.51.100.{i}"})
    ok = client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=zainab)
    assert ok.status_code == 200, ok.text


# ---------------------------------------------------------------- PII never in the audit trail

def test_cnic_and_iban_in_free_text_are_masked_in_the_audit_trail(client, login, file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    reason = f"My CNIC is {ZAINAB_CNIC} and account PK00MOCK0000000000000001, please check"
    assert client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": reason}, headers=login("zainab")).status_code == 200
    row = db.execute(select(AuditEvent).where(AuditEvent.action == "CASE_ESCALATED").order_by(AuditEvent.seq.desc())).scalars().first()
    text = str(row.details)
    assert ZAINAB_CNIC not in text and "PK00MOCK0000000000000001" not in text
    assert ZAINAB_CNIC[-4:] in text
    assert client.get("/api/v1/audit/verify", headers=login("auditor")).json()["data"]["intact"] is True


def test_denied_path_with_a_cnic_is_masked(client, login, db):
    assert client.get(f"/mock/identity/persons/{ZAINAB_CNIC}", headers=login("helper")).status_code == 403
    rows = db.execute(select(AuditEvent.resource).where(AuditEvent.action == "ACCESS_DENIED")).scalars().all()
    assert rows and all(ZAINAB_CNIC not in (r or "") for r in rows)


def test_redact_masks_cnic_forms_and_leaves_hashes_alone():
    from app.core.redact import redact, redact_text

    assert redact_text("cnic 90000-0000002-2 ok") == "cnic " + "*" * 11 + "02-2 ok"
    assert redact_text("9000000000022") == "*********0022"
    sha = "a" * 20 + "9000000000022" + "b" * 31
    assert redact_text(sha) == sha  # digits inside a hex hash are not a CNIC
    original = {"a": ["9000000000022"]}
    assert redact(original) == {"a": ["*********0022"]} and original == {"a": ["9000000000022"]}


def test_access_log_lines_are_redacted():
    import logging

    from app.core.redact import RedactingFilter

    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/1.1" %d', ("1.2.3.4", "GET", f"/mock/identity/persons/{ZAINAB_CNIC}", 200), None)
    RedactingFilter().filter(record)
    assert ZAINAB_CNIC not in record.getMessage()
