"""Adversarial corpus: scams must never be LOOKS_GENUINE (Jev honest or steered); benign must never be LIKELY_SCAM.
Prints false-alarm and miss rates. The corpus lives in data/scam_corpus.json for the evaluation page."""
import json
from pathlib import Path

import pytest

from app.services import scam

CORPUS = json.loads((Path(__file__).parent / "data" / "scam_corpus.json").read_text(encoding="utf-8"))["messages"]
SCAMS = [m for m in CORPUS if m["label"] == "scam"]
BENIGN = [m for m in CORPUS if m["label"] == "benign"]
SECRET = "test-secret-" + "x" * 32
HONEST_SCAM = {"asks_fee": 0.9, "has_link": 0.9, "claims_government": 0.9, "claims_payment_ready": 0.9, "urgency": 0.5}
STEERED: dict[str, float] = {}  # Jev fooled: every answer near zero
MODES = ("honest", "steered", "offline")


def _stub(monkeypatch, probabilities):
    base = {k: probabilities.get(k, 0.01) for k in scam.QUESTIONS}
    monkeypatch.setattr(scam, "_jev_signals", lambda text: (dict(base), "jev-stub"))


def _honest_benign(row):
    return {"claims_government": 0.9, "claims_payment_ready": 0.5} if row["tactic"] == "official_info" else {}


@pytest.fixture(autouse=True)
def fresh_state():
    scam.split_memory.clear()
    scam.breaker.reset()
    yield
    scam.split_memory.clear()
    scam.breaker.reset()


def _verdict(monkeypatch, row, mode, user="u1"):
    if mode == "offline":
        return scam.check(None, row["text"], row["sender"], None, None, use_jev=False)
    honest = HONEST_SCAM if row["label"] == "scam" else _honest_benign(row)
    _stub(monkeypatch, honest if mode == "honest" else STEERED)
    return scam.check(None, row["text"], row["sender"], None, None, user_key=user, secret=SECRET)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("row", SCAMS, ids=[m["id"] for m in SCAMS])
def test_scam_is_never_looks_genuine(monkeypatch, row, mode):
    result = _verdict(monkeypatch, row, mode)
    assert result.verdict != "LOOKS_GENUINE", (row["id"], result.signals)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("row", BENIGN, ids=[m["id"] for m in BENIGN])
def test_benign_is_never_likely_scam(monkeypatch, row, mode):
    result = _verdict(monkeypatch, row, mode)
    assert result.verdict != "LIKELY_SCAM", (row["id"], result.signals)


def test_split_fee_then_link_raises_the_floor(monkeypatch):
    fee, link = (next(m for m in SCAMS if m["id"] == i) for i in ("split_fee_part", "split_link_part"))
    _verdict(monkeypatch, fee, "steered", user="split-user")
    second = _verdict(monkeypatch, link, "steered", user="split-user")
    assert second.verdict == "LIKELY_SCAM" and second.signals["split_message"]
    assert not _verdict(monkeypatch, link, "steered", user="someone-else").signals["split_message"]


def test_print_rates(monkeypatch, capsys):
    lines = []
    for mode in MODES:
        verdicts = []
        for row in CORPUS:
            scam.split_memory.clear()
            verdicts.append((row["label"], _verdict(monkeypatch, row, mode).verdict))
        miss = sum(lab == "scam" and v == "LOOKS_GENUINE" for lab, v in verdicts) / len(SCAMS)
        not_flagged = sum(lab == "scam" and v != "LIKELY_SCAM" for lab, v in verdicts) / len(SCAMS)
        false_alarm = sum(lab == "benign" and v == "LIKELY_SCAM" for lab, v in verdicts) / len(BENIGN)
        benign_unsure = sum(lab == "benign" and v == "NOT_SURE" for lab, v in verdicts) / len(BENIGN)
        lines.append(f"[{mode}] miss (scam->LOOKS_GENUINE)={miss:.0%}  scam not LIKELY_SCAM={not_flagged:.0%}  "
                     f"false alarm (benign->LIKELY_SCAM)={false_alarm:.0%}  benign NOT_SURE={benign_unsure:.0%}")
        assert miss == 0 and false_alarm == 0
    with capsys.disabled():
        print(f"\nScam corpus ({len(SCAMS)} scam, {len(BENIGN)} benign):\n  " + "\n  ".join(lines))
