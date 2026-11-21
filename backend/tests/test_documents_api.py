"""Document API: upload -> indicators -> decision route; auth, consent, limits, officer view."""
import io

import pytest
from PIL import Image, ImageFilter

from app.documents import service
from app.documents.ocr import OcrUnavailable
from app.models.audit import AuditEvent
from tests.doc_fixtures import death_certificate, sample


@pytest.fixture
def ocr_returns(monkeypatch):
    def _set(result):
        def fake(_img, *args, **kwargs):
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr(service, "run_ocr", fake)
    return _set


def _upload(client, headers, case_id, name, kind="death_certificate", content_type=None):
    data = sample(name) if isinstance(name, str) else name
    ctype = content_type or ("image/png" if str(name).endswith(".png") else "image/jpeg")
    return client.post(f"/api/v1/cases/{case_id}/documents", data={"kind": kind},
                       files={"file": ("photo", data, ctype)}, headers=headers)


def _route(client, headers, case_id):
    return client.get(f"/api/v1/cases/{case_id}", headers=headers).json()["data"]["latest_decision"]


def test_clean_certificate_keeps_the_clean_claim_approved(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate())
    case = file_claim("zainab")["data"]
    assert case["status"] == "auto_approved"
    zainab = login("zainab")
    response = _upload(client, zainab, case["id"], "death_certificate_aslam.whatsapp.jpg")
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["risk_level"] == "low" and body["case_status"] == "auto_approved"
    assert body["fields"]["date_of_death"]["value"] == "2026-08-14"
    assert "indicators" not in body  # citizens never see forensic detail


def test_edited_certificate_goes_to_an_officer_with_evidence(client, login, file_claim, ocr_returns, db):
    ocr_returns(death_certificate(name="Mohd. Akram", date_text="14.06.2026"))
    case = file_claim("zainab")["data"]
    response = _upload(client, login("zainab"), case["id"], "death_certificate_aslam_edited.whatsapp.jpg")
    body = response.json()["data"]
    assert body["risk_level"] == "officer" and body["case_status"] == "in_review"
    assert any(r["code"] == "NEEDS_OFFICER" for r in body["reasons"])
    assert all("fake" not in r["text_en"].lower() for r in body["reasons"])
    officer = login("officer")
    decision = _route(client, officer, case["id"])
    assert decision["route"] == "UNSURE" and "DOC_EDIT_RISK" in decision["reason_codes"]

    docs = client.get(f"/api/v1/cases/{case['id']}/documents", headers=officer).json()["data"]
    codes = {i["code"] for i in docs[0]["indicators"]}
    assert {"STAMP_DUPLICATED", "RECORD_MISMATCH"} <= codes
    mismatched = {c["field"] for c in docs[0]["checks"] if c["status"] == "mismatch"}
    assert {"name_of_deceased", "date_of_death"} <= mismatched
    ela = client.get(f"/api/v1/cases/{case['id']}/documents/{docs[0]['id']}/ela", headers=officer)
    assert ela.status_code == 200 and ela.headers["content-type"] == "image/jpeg" and ela.content[:2] == b"\xff\xd8"
    actions = {a for (a,) in db.query(AuditEvent.action).filter(AuditEvent.case_id == case["id"]).all()}
    assert {"DOCUMENT_UPLOADED", "DOCUMENT_ANALYSED", "DOCUMENT_IMAGE_VIEWED"} <= actions


def test_record_mismatch_alone_asks_for_proof(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate(date_text="14.06.2026"))  # clean image, but the date disagrees with the record
    case = file_claim("zainab")["data"]
    body = _upload(client, login("zainab"), case["id"], "death_certificate_aslam.png").json()["data"]
    assert body["risk_level"] == "mismatch" and body["case_status"] == "proof_requested"
    decision = _route(client, login("officer"), case["id"])
    assert decision["route"] == "ASK_PROOF" and "DOC_MISMATCH" in decision["reason_codes"]


def test_low_confidence_mismatch_asks_the_citizen_to_confirm_then_rechecks(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate(date_text="14.06.2026", conf=0.6))
    case = file_claim("zainab")["data"]
    zainab = login("zainab")
    body = _upload(client, zainab, case["id"], "death_certificate_aslam.png").json()["data"]
    assert body["risk_level"] == "confirm" and body["case_status"] == "auto_approved"
    assert body["fields"]["date_of_death"]["needs_confirmation"]
    confirmed = client.post(f"/api/v1/cases/{case['id']}/documents/{body['id']}/confirm",
                            json={"values": {"date_of_death": "2026-08-14", "name_of_deceased": "Mohd. Aslam"}}, headers=zainab)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["risk_level"] == "low"
    # A typed value is held to the same record: a wrong correction becomes a mismatch.
    wrong = client.post(f"/api/v1/cases/{case['id']}/documents/{body['id']}/confirm",
                        json={"values": {"date_of_death": "2026-01-01"}}, headers=zainab).json()["data"]
    assert wrong["risk_level"] == "mismatch" and wrong["case_status"] == "proof_requested"


def test_ocr_unavailable_means_an_officer_reads_it_not_a_failure(client, login, file_claim, ocr_returns):
    ocr_returns(OcrUnavailable("no engine"))
    case = file_claim("zainab")["data"]
    body = _upload(client, login("zainab"), case["id"], "cnic_front_zainab.png", kind="claimant_cnic").json()["data"]
    assert [r["code"] for r in body["reasons"]] == ["OCR_UNAVAILABLE"]
    assert body["risk_level"] == "low" and body["fields"] == {}


def test_blurry_photo_is_sent_back_and_not_stored(client, login, file_claim, db):
    case = file_claim("zainab")["data"]
    img = Image.open(io.BytesIO(sample("cnic_front_zainab.png"))).convert("RGB").filter(ImageFilter.GaussianBlur(4))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    response = _upload(client, login("zainab"), case["id"], buf.getvalue(), kind="claimant_cnic", content_type="image/jpeg")
    body = response.json()["data"]
    assert body["status"] == "retake" and "blurry" in body["quality"]["problems"]
    assert body["reasons"][0]["text_ur"]
    assert client.get(f"/api/v1/cases/{case['id']}/documents", headers=login("zainab")).json()["data"] == []


def test_upload_limits_type_size_and_kind(client, login, file_claim, monkeypatch):
    case = file_claim("zainab")["data"]
    zainab = login("zainab")
    assert _upload(client, zainab, case["id"], b"%PDF-1.4", content_type="application/pdf").status_code == 415
    assert _upload(client, zainab, case["id"], b"not really a png", content_type="image/png").status_code == 422
    assert _upload(client, zainab, case["id"], "cnic_front_zainab.png", kind="passport").status_code == 422
    monkeypatch.setattr("app.api.documents.MAX_UPLOAD_BYTES", 1000)
    assert _upload(client, zainab, case["id"], "cnic_front_zainab.png").status_code == 413


def test_other_citizens_auditors_and_withdrawn_consent_are_refused(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate())
    case = file_claim("zainab")["data"]
    doc = _upload(client, login("zainab"), case["id"], "death_certificate_aslam.png").json()["data"]
    assert _upload(client, login("rukhsana"), case["id"], "death_certificate_aslam.png").status_code == 403
    assert client.get(f"/api/v1/cases/{case['id']}/documents", headers=login("rukhsana")).status_code == 403
    assert client.get(f"/api/v1/cases/{case['id']}/documents/{doc['id']}/ela", headers=login("zainab")).status_code == 403
    assert _upload(client, login("auditor"), case["id"], "death_certificate_aslam.png").status_code == 403
    assert client.post(f"/api/v1/cases/{case['id']}/documents", data={"kind": "frc"}).status_code == 401
    assert client.get(f"/api/v1/cases/{case['id']}/documents/{doc['id']}/image", headers=login("welfare_officer")).status_code == 403

    zainab = login("zainab")
    consents = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    department = next(c for c in consents if c["grantee_type"] == "department" and c["status"] == "active")
    assert client.post(f"/api/v1/me/consents/{department['id']}/withdraw", headers=zainab).status_code == 200
    assert client.get(f"/api/v1/cases/{case['id']}/documents", headers=login("officer")).status_code == 403
