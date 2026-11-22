"""Red-team regressions through the document API (H2, M3, M4). Jev and Azure are stubbed."""
import pytest

from app.documents import service
from app.documents.ocr import OcrLine, OcrResult
from app.documents.signals import document_signals
from app.models.audit import AuditEvent
from tests.doc_fixtures import death_certificate, sample


@pytest.fixture
def ocr_returns(monkeypatch):
    def _set(result):
        monkeypatch.setattr(service, "run_ocr", lambda _img, *a, **k: result)
    return _set


def _upload(client, headers, case_id, name, kind="death_certificate"):
    data = sample(name)
    ctype = "image/png" if name.endswith(".png") else "image/jpeg"
    return client.post(f"/api/v1/cases/{case_id}/documents", data={"kind": kind},
                       files={"file": ("photo", data, ctype)}, headers=headers)


def _docs(client, officer, case_id):
    return client.get(f"/api/v1/cases/{case_id}/documents", headers=officer).json()["data"]


def _codes(doc):
    return {i["code"] for i in doc["indicators"]}


# ---------- H2 sticky high risk ----------

def test_h2_clean_reupload_does_not_erase_the_flag(client, login, file_claim, ocr_returns, db):
    zainab = login("zainab")
    ocr_returns(death_certificate(name="Mohd. Akram", date_text="14.06.2026"))
    case = file_claim("zainab")["data"]
    first = _upload(client, zainab, case["id"], "death_certificate_aslam_edited.whatsapp.jpg").json()["data"]
    assert first["case_status"] == "in_review"
    ocr_returns(death_certificate())
    second = _upload(client, zainab, case["id"], "death_certificate_aslam.png").json()["data"]
    assert second["case_status"] != "auto_approved"
    assert document_signals(db, case["id"])["high"] == ["death_certificate"]
    latest = _docs(client, login("officer"), case["id"])[-1]
    repeated = next(i for i in latest["indicators"] if i["code"] == "REPEATED_UPLOAD")
    assert repeated["evidence"]["earlier_flagged"] == [first["id"]]


def test_h2_only_an_officer_can_clear_and_it_is_audited(client, login, file_claim, ocr_returns, db):
    zainab, officer = login("zainab"), login("officer")
    ocr_returns(death_certificate(name="Mohd. Akram", date_text="14.06.2026"))
    case = file_claim("zainab")["data"]
    flagged = _upload(client, zainab, case["id"], "death_certificate_aslam_edited.whatsapp.jpg").json()["data"]
    url = f"/api/v1/cases/{case['id']}/documents/{flagged['id']}/clear"
    body = {"reason": "Compared with the union council register by phone"}
    for who in ("zainab", "helper", "admin", "auditor"):
        assert client.post(url, json=body, headers=login(who)).status_code == 403
    assert client.post(url, json={"reason": "ok"}, headers=officer).status_code == 422
    response = client.post(url, json=body, headers=officer)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["cleared"]["reason"] == body["reason"]
    assert document_signals(db, case["id"])["high"] == []
    assert client.post(url, json=body, headers=officer).status_code == 409
    assert db.query(AuditEvent).filter(AuditEvent.case_id == case["id"], AuditEvent.action == "DOCUMENT_RISK_CLEARED").count() == 1


def test_h2_clearing_a_paper_that_is_not_flagged_is_refused(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate())
    case = file_claim("zainab")["data"]
    doc = _upload(client, login("zainab"), case["id"], "death_certificate_aslam.png").json()["data"]
    r = client.post(f"/api/v1/cases/{case['id']}/documents/{doc['id']}/clear",
                    json={"reason": "nothing to clear here at all"}, headers=login("officer"))
    assert r.status_code == 409


# ---------- M3 confirm ----------

def _wrong_cert_number():
    res = death_certificate()
    return OcrResult(res.engine, [OcrLine("Reg. No. DC-UC99-2026-9999", line.confidence, line.box)
                                  if line.text.startswith("Reg. No.") else line for line in res.lines])


def test_m3_clearly_read_field_cannot_be_overwritten(client, login, file_claim, ocr_returns):
    ocr_returns(_wrong_cert_number())
    case = file_claim("zainab")["data"]
    zainab = login("zainab")
    doc = _upload(client, zainab, case["id"], "death_certificate_aslam.png").json()["data"]
    assert doc["risk_level"] == "mismatch"
    for value in ("-", "DC-UC12-2026-0412"):
        r = client.post(f"/api/v1/cases/{case['id']}/documents/{doc['id']}/confirm",
                        json={"values": {"certificate_no": value}}, headers=zainab)
        assert r.status_code == 422


def test_m3_junk_values_rejected_and_typed_resolution_shown_to_officer(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate(date_text="14.06.2026", conf=0.6))  # unclear date, low confidence
    case = file_claim("zainab")["data"]
    zainab = login("zainab")
    doc = _upload(client, zainab, case["id"], "death_certificate_aslam.png").json()["data"]
    url = f"/api/v1/cases/{case['id']}/documents/{doc['id']}/confirm"
    for junk in ("-", "..", "ab", "not a date"):
        assert client.post(url, json={"values": {"date_of_death": junk}}, headers=zainab).status_code == 422
    ok = client.post(url, json={"values": {"date_of_death": "14.08.2026"}}, headers=zainab)
    assert ok.status_code == 200, ok.text
    officer_doc = _docs(client, login("officer"), case["id"])[-1]
    assert "date_of_death" in officer_doc["resolved_by_claimant"]
    assert "RESOLVED_BY_TYPING" in _codes(officer_doc)
    assert client.post(url, json={"values": {"date_of_death": "15.08.2026"}}, headers=zainab).status_code == 422  # typed once


# ---------- M4 unverified ----------

def test_m4_blank_ocr_is_unverified_not_clean(client, login, file_claim, ocr_returns, db):
    ocr_returns(OcrResult("tesseract", []))
    case = file_claim("zainab")["data"]
    r = _upload(client, login("zainab"), case["id"], "death_certificate_aslam.png").json()["data"]
    assert r["risk_level"] == "unverified" and r["status"] == "unverified"
    assert any(x["text_en"].startswith("We could not read this paper") for x in r["reasons"])
    signals = document_signals(db, case["id"])
    assert "death_certificate" not in signals["analysed"] and signals["unverified"] == ["death_certificate"]
