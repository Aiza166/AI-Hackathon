"""Scam Shield (Challenge 8): content beats sender, the citizen's case is cross-checked,
and when the checker is unsure or offline it says NOT_SURE instead of guessing."""
import pytest

from app.decision.jev_client import JevResult
from app.services import scam

FEE_SCAM = "Your pension is released! Pay Rs 5000 processing fee today at pension-release.example.com or it will be cancelled."
GENUINE = "Your claim SP-1042 has been received. An officer will review it within 7 working days. No fee is charged."


def _fake_jev(probabilities: dict[str, float]):
    def ask(self, state, questions):
        return JevResult(model="jev-1.14.0", answers={k: {"type": "noul", "noul": probabilities.get(k, 0.02)} for k in questions}, latency_ms=5)
    return ask


@pytest.fixture
def jev(monkeypatch):
    def use(probabilities: dict[str, float]):
        monkeypatch.setattr("app.decision.jev_client.JevClient.ask", _fake_jev(probabilities))
    return use


def _check(client, headers, text, **extra):
    return client.post("/api/v1/scam/check", json={"text": text, **extra}, headers=headers).json()["data"]


def test_fee_scam_is_flagged_with_reasons_and_case_cross_check(client, login, jev):
    jev({"asks_fee": 0.98, "has_link": 0.97, "claims_government": 0.9, "urgency": 0.9, "claims_payment_ready": 0.95})
    result = _check(client, login("rafiq"), FEE_SCAM, sender="0300-0000000")
    assert result["verdict"] == "LIKELY_SCAM"
    assert result["model_id"] == "jev-1.14.0"
    assert any("fee" in r for r in result["reasons"])
    assert result["case_cross_check"] == "Your claim shows no payment waiting for you."
    assert result["report_routes"]


def test_genuine_message_looks_genuine(client, login, jev):
    jev({"claims_government": 0.6})
    result = _check(client, login("zainab"), GENUINE, sender="PENSION-GOV")
    assert result["verdict"] == "LOOKS_GENUINE"
    assert result["report_routes"] == []


def test_borderline_money_signal_says_not_sure(client, login, jev):
    jev({"asks_fee": 0.5})
    result = _check(client, login("zainab"), "Visit the office with Rs 100 for the stamp paper if needed.")
    assert result["verdict"] == "NOT_SURE"


def test_someone_on_the_phone_raises_the_risk(client, login, jev):
    jev({"asks_secret": 0.75})
    calm = _check(client, login("zainab"), "Please share the code you received.")
    pressured = _check(client, login("zainab"), "Please share the code you received.", on_call_with_unknown=True)
    assert pressured["confidence"] > calm["confidence"]
    assert pressured["verdict"] == "LIKELY_SCAM"


def test_without_jev_the_fallback_never_says_genuine(client, login):
    # Tests run with no Jev key, so the keyword fallback is used.
    result = _check(client, login("zainab"), GENUINE, sender="PENSION-GOV")
    assert result["model_id"] is None
    assert result["verdict"] == "NOT_SURE"


def test_hidden_characters_are_removed_before_checking():
    assert scam.normalise("pa​y fee") == "pay fee"


def test_scam_map_counts_without_storing_text(client, login, jev, db):
    jev({"asks_fee": 0.98})
    _check(client, login("rafiq"), FEE_SCAM, area="Karachi South")
    data = client.get("/api/v1/scam/map", headers=login("officer")).json()["data"]
    assert data["scams_by_type"] == {"fee": 1}
    assert data["scams_by_area"] == {"Karachi South": 1}
    from app.models.scam import ScamCheck

    stored = db.query(ScamCheck).one()
    assert FEE_SCAM not in str(stored.signals) and len(stored.text_hash) == 64


def test_api_key_with_scam_scope_can_check(client, login, jev):
    jev({"asks_fee": 0.98})
    key = client.post("/api/v1/admin/api-keys", json={"name": "SMS gateway", "scopes": ["scam:check"]}, headers=login("admin")).json()["data"]["api_key"]
    response = client.post("/api/v1/public/scam/check", json={"text": FEE_SCAM}, headers={"X-API-Key": key})
    assert response.status_code == 200
    assert response.json()["data"]["verdict"] == "LIKELY_SCAM"


def test_scam_verdict_lists_real_report_routes_with_1799_and_no_1991(client, login, jev):
    jev({"asks_fee": 0.98, "has_link": 0.97, "claims_government": 0.9, "claims_payment_ready": 0.95})
    routes = _check(client, login("rafiq"), FEE_SCAM)["report_routes"]
    urls = [r["url"] for r in routes]
    assert "tel:1799" in urls and "https://complaint.pta.gov.pk/" in urls and "https://sunwai.sbp.org.pk/" in urls
    assert not any("1991" in (u or "") for u in urls)
    assert all(r["name"] and r["name_ur"] and r["confidence"] for r in routes)
    assert "tel:080026477" not in urls  # BISP line only when the message is about BISP


def test_bisp_message_adds_the_bisp_helpline(client, login, jev):
    jev({"asks_fee": 0.98, "claims_government": 0.9})
    text = "BISP: your Benazir payment is ready, pay Rs 2000 fee to receive it."
    routes = _check(client, login("rafiq"), text, sender="8171")["report_routes"]
    assert "tel:080026477" in [r["url"] for r in routes]
