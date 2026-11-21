"""Per-tier evaluation (deterministic / Jev only / cascade) with every sensor mocked: structure,
metrics and cost accounting. Live numbers come from `python -m app.evaluation.runner --live`."""
import re

from app.ai.second_sensor import SecondSensor, SensorAnswers
from app.decision.jev_client import JevResult
from app.documents.jev_checks import JevDocResult
from app.evaluation import doc_eval, scam_eval

FEE = re.compile(r"fee|rupay|rs\s?\d|روپے|فیس|easypaisa", re.I)
CODE = re.compile(r"code|pin|otp|کوڈ|پن", re.I)


def _fake_jev(self, state, questions):
    text = state["untrusted_message"]
    answers = {q: 0.03 for q in questions}
    answers["asks_fee"] = 0.95 if FEE.search(text) and "no fee" not in text.lower() else 0.04
    answers["asks_secret"] = 0.5 if CODE.search(text) else 0.04  # undecided: the cascade should step in
    return JevResult(model="jev-1.14.0", answers={k: {"noul": v} for k, v in answers.items()}, latency_ms=900, usage={"input_tokens": 600})


def _fake_second(self, questions, untrusted_text=None, image_jpeg=None):
    text = untrusted_text or ""
    probabilities = {q: 0.05 for q in questions}
    if "asks_secret" in questions:
        warns = re.search(r"never share|do not share|mat batana|نہ دیں|مت بتانا", text, re.I)
        probabilities["asks_secret"] = 0.05 if warns else 0.95 if CODE.search(text) else 0.05
    return SensorAnswers(status="ok", model="gpt-4o-mini", probabilities=probabilities, latency_ms=400, cost_usd=0.00008)


def _mock(monkeypatch):
    monkeypatch.setattr("app.decision.jev_client.JevClient.ask", _fake_jev)
    monkeypatch.setattr(SecondSensor, "configured", property(lambda self: True))
    monkeypatch.setattr(SecondSensor, "ask", _fake_second)


def test_every_scam_tier_reports_accuracy_rates_latency_and_cost(monkeypatch):
    _mock(monkeypatch)
    result = scam_eval.evaluate_scam(tiers=tuple(scam_eval.TIERS))
    assert result["n"] == 80 and result["primary_tier"] == "cascade" and result["mode"] == "mocked"
    for name in ("deterministic", "jev_only", "cascade"):
        tier = result["tiers"][name]
        assert tier["status"] == "ran"
        assert {"accuracy", "fpr", "fnr", "not_sure_rate", "median_latency_ms", "p95_latency_ms", "cost_per_check_usd"} <= set(tier)
        assert set(tier["by_channel"]) == {"sms", "whatsapp", "call"}
    assert result["tiers"]["deterministic"]["total_cost_usd"] == 0.0
    assert result["tiers"]["jev_only"]["second_sensor_calls"] == 0
    cascade = result["tiers"]["cascade"]
    assert cascade["second_sensor_calls"] > 0 and cascade["total_cost_usd"] > result["tiers"]["jev_only"]["total_cost_usd"]
    assert cascade["second_sensor_calls"] < cascade["n"]  # only when needed, not on every message
    assert all(set(item["tier_verdicts"]) == {"deterministic", "jev_only", "cascade"} for item in result["items"])


def test_cascade_beats_jev_alone_when_jev_is_undecided(monkeypatch):
    _mock(monkeypatch)
    tiers = scam_eval.evaluate_scam(tiers=("jev_only", "cascade"))["tiers"]
    assert tiers["cascade"]["not_sure_rate"] < tiers["jev_only"]["not_sure_rate"]
    assert tiers["cascade"]["fnr"] <= tiers["jev_only"]["fnr"]


def test_document_tiers_with_mocked_sensors(monkeypatch):
    def fake_doc_jev(kind, img, settings=None, client=None):
        return JevDocResult(status="ok", model="jev-1.14.0", latency_ms=1200,
                            answers={"right_type": {"p": 0.95, "band": "yes"}, "text_altered": {"p": 0.45, "band": "undecided"},
                                     "screen_photo": {"p": 0.1, "band": "no"}, "stamp_present": {"p": 0.9, "band": "yes"}})
    monkeypatch.setattr(doc_eval.jev_checks, "ask_document_questions", fake_doc_jev)
    monkeypatch.setattr(SecondSensor, "configured", property(lambda self: True))
    monkeypatch.setattr(SecondSensor, "ask", lambda self, q, untrusted_text=None, image_jpeg=None: SensorAnswers(
        status="ok", model="gpt-4o-mini", probabilities={k: (0.05 if k == "text_altered" else 0.9) for k in q},
        latency_ms=800, cost_usd=0.0004))
    result = doc_eval.evaluate_documents(tiers=doc_eval.TIERS)["tiers"]
    assert result["deterministic"]["fnr"] == 0.0 and result["deterministic"]["fpr"] == 0.0
    assert result["jev_only"]["undecided_rate"] == 1.0  # Jev undecided on "text altered" everywhere
    assert result["cascade"]["undecided_rate"] < 1.0 and result["cascade"]["total_cost_usd"] > 0
    # The edited certificate: copy-move says yes, second sensor says no -> disagreement, still flagged for a person.
    edited = [r for r in result["cascade"]["items"] if r["edited"]]
    assert all(r["outcome"] == "flag" for r in edited)


def test_offline_documents_eval_runs_only_deterministic():
    result = doc_eval.evaluate_documents()["tiers"]
    assert result["deterministic"]["status"] == "ran" and result["jev_only"]["status"] == "not_run"
