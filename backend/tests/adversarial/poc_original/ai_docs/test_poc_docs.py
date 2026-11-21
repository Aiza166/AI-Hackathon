import sys
sys.path.insert(0, r"C:/Users/aizag/Desktop/ai hackathon/team-repo/backend")
import pytest
from app.documents import service
from app.documents.ocr import OcrResult, OcrLine
from tests.doc_fixtures import death_certificate, sample, L
from tests.test_documents_api import _upload, _route, ocr_returns  # reuse helpers

def status(client, h, cid):
    return client.get(f"/api/v1/cases/{cid}", headers=h).json()["data"]["status"]

def test_reupload_clears_forgery_flag(client, login, file_claim, ocr_returns):
    z = login("zainab")
    ocr_returns(death_certificate(name="Mohd. Akram", date_text="14.06.2026"))
    case = file_claim("zainab")["data"]
    r = _upload(client, z, case["id"], "death_certificate_aslam_edited.whatsapp.jpg").json()["data"]
    print("\n[1] forged upload -> risk", r["risk_level"], "case_status", r["case_status"])
    # officer escalates manually (in_review, not final)
    # attacker immediately re-uploads a clean photo of the same kind
    ocr_returns(death_certificate())
    r2 = _upload(client, z, case["id"], "death_certificate_aslam.png").json()["data"]
    print("[2] re-upload clean -> risk", r2["risk_level"], "case_status", r2["case_status"])
    docs = client.get(f"/api/v1/cases/{case['id']}/documents", headers=login("officer")).json()["data"]
    print("    docs stored:", [(d["risk_level"]) for d in docs], "route:", _route(client, login("officer"), case["id"])["route"])
    assert r2["case_status"] == "auto_approved"

def test_confirm_blank_certificate_no_clears_mismatch(client, login, file_claim, ocr_returns):
    from app.documents.fields import Field
    z = login("zainab")
    res = death_certificate()
    lines = [OcrLine("Reg. No. DC-UC99-2026-9999", l.confidence, l.box) if l.text.startswith("Reg. No.") else l for l in res.lines]
    ocr_returns(OcrResult(res.engine, lines))
    case = file_claim("zainab")["data"]
    r = _upload(client, z, case["id"], "death_certificate_aslam.png").json()["data"]
    print("\n[3] wrong certificate no -> risk", r["risk_level"], r["case_status"], "cert no read:", r["fields"].get("certificate_no"))
    c = client.post(f"/api/v1/cases/{case['id']}/documents/{r['id']}/confirm", json={"values": {"certificate_no": "-"}}, headers=z).json()["data"]
    print("[4] confirm certificate_no='-' ->", c["risk_level"], c["case_status"])
    assert c["risk_level"] == "low"

def test_blank_text_image_is_clean(client, login, file_claim, ocr_returns):
    ocr_returns(OcrResult("tesseract", []))
    case = file_claim("zainab")["data"]
    r = _upload(client, login("zainab"), case["id"], "death_certificate_aslam.png", kind="death_certificate").json()["data"]
    print("\n[5] OCR reads nothing (any good-quality image) -> risk", r["risk_level"], r["case_status"], "reasons", r["reasons"])
    assert r["risk_level"] == "low"

def test_wrong_kind_and_same_bytes_twice(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate())
    case = file_claim("zainab")["data"]
    z = login("zainab")
    a = _upload(client, z, case["id"], "death_certificate_aslam.png").json()["data"]
    b = _upload(client, z, case["id"], "death_certificate_aslam.png").json()["data"]
    o = login("officer")
    docs = client.get(f"/api/v1/cases/{case['id']}/documents", headers=o).json()["data"]
    print("\n[6] same bytes twice ->", [(d["sha256"][:8], d["risk_level"]) for d in docs], "no DUPLICATE_DOCUMENT indicator:", all("DUP" not in c for d in docs for i in d["indicators"] for c in [i["code"]]))

def test_retry_loop_no_attempt_limit(client, login, file_claim, ocr_returns):
    ocr_returns(death_certificate())
    case = file_claim("zainab")["data"]
    z = login("zainab")
    codes = []
    for i in range(9):
        r = _upload(client, z, case["id"], "death_certificate_aslam.png")
        codes.append(r.status_code)
    print("\n[7] 9 uploads in a row ->", codes, "(limit is 10/min per client IP)")
    # spoof X-Forwarded-For does not matter in TestClient; see report for uvicorn analysis
