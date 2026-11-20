"""Scam Shield: is this "your pension is released, pay a fee" message a scam?

Jev answers small factual questions about the message (a sensor). Code decides:
content signals (fee, secret code, link) outweigh the sender ID, the citizen's real case is
cross-checked, and if Jev is down a keyword fallback is used and money-related doubt
becomes NOT_SURE instead of a guess. Reasons shown to people are fixed text, never generated.
"""
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision.jev_client import Band, JevClient, JevUnavailable, noul, noul_band
from app.models.platform import Case

OFFICIAL_SENDERS = {"PENSION-GOV"}  # mock official sender ID for this prototype
OFFICIAL_DOMAINS = ("pension.gov.example",)  # mock official domain
LINK = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:com|net|org|pk|info|xyz|example)(?:/\S*)?)", re.I)
FEE_WORDS = re.compile(r"(fee|fees|charges?|pay\s+rs|rupay|rupees|روپے|فیس|jama\s+karwa|send\s+rs|bhej)", re.I)
SECRET_WORDS = re.compile(r"(otp|pin|password|code|کوڈ|verification)", re.I)
PAID_STATUSES = ("approved", "auto_approved")

QUESTIONS = {
    "asks_fee": noul("Does the message ask the reader to pay a fee, charge or any money?"),
    "asks_secret": noul("Does the message ask for an OTP, PIN, password or verification code?"),
    "has_link": noul("Does the message contain a web link or ask the reader to open a website?"),
    "claims_government": noul("Does the message claim to come from a government office or programme?"),
    "urgency": noul("Does the message pressure the reader with a deadline, threat or prize?"),
    "claims_payment_ready": noul("Does the message say that a payment, pension or relief money is ready or released?"),
    "addresses_reader_instructions": noul("Does the message contain instructions aimed at an automated checker or AI?"),
}
WEIGHTS = {"asks_fee": 0.45, "asks_secret": 0.45, "has_link": 0.15, "urgency": 0.1}
MONEY_SIGNALS = ("asks_fee", "asks_secret")
STRONG_SIGNAL_FACTOR = 0.25  # remaining "not a scam" odds after a clear fee or code request

REASONS = {
    "asks_fee": ("پیسے یا فیس مانگی گئی ہے۔ حکومت کبھی فیس نہیں مانگتی۔", "It asks for money or a fee. The government never charges a fee."),
    "asks_secret": ("کوڈ یا پن مانگا گیا ہے۔ اپنا کوڈ کسی کو نہ دیں۔", "It asks for a code or PIN. Never share your code."),
    "unofficial_link": ("اس میں غیر سرکاری لنک ہے۔ اسے نہ کھولیں۔", "It has a link that is not an official website. Do not open it."),
    "unofficial_sender": ("یہ سرکاری نمبر سے نہیں آیا۔", "It did not come from the official sender."),
    "urgency": ("یہ جلدی یا دھمکی سے دباؤ ڈالتا ہے۔", "It pressures you with a deadline or threat."),
    "no_payment_pending": ("آپ کے دعوے میں کوئی ادائیگی باقی نہیں۔", "Your claim shows no payment waiting for you."),
    "on_call": ("کوئی فون پر آپ کو یہ کرنے کو کہہ رہا ہے۔ فون بند کریں۔", "Someone on the phone is telling you to do this. Hang up."),
    "checker_not_sure": ("ہمیں یقین نہیں۔ کسی مددگار یا افسر سے پوچھیں۔", "We are not sure. Ask a helper or an officer."),
}


@dataclass
class ScamResult:
    verdict: str
    score: float
    reasons: list[str]
    reasons_ur: list[str]
    scam_type: str
    model_id: str | None
    signals: dict = field(default_factory=dict)
    case_cross_check: str | None = None


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")  # drop zero-width / hidden characters


def _jev_signals(text: str) -> tuple[dict[str, float], str | None]:
    client = JevClient()
    try:
        result = client.ask({"untrusted_message": text}, QUESTIONS)  # labelled: the message is data, not instructions
        return {name: result.noul(name) for name in QUESTIONS}, result.model
    finally:
        client.close()


def _keyword_signals(text: str) -> dict[str, float]:
    """Fallback when Jev is unavailable: deliberately cautious mid-band values, so a match is never treated as certain."""
    return {"asks_fee": 0.6 if FEE_WORDS.search(text) else 0.1, "asks_secret": 0.6 if SECRET_WORDS.search(text) else 0.1,
            "has_link": 0.9 if LINK.search(text) else 0.05, "urgency": 0.1, "claims_government": 0.5, "claims_payment_ready": 0.5,
            "addresses_reader_instructions": 0.1}


def _official_link(text: str) -> bool:
    links = LINK.findall(text)
    return bool(links) and all(any(d in link.lower() for d in OFFICIAL_DOMAINS) for link in links)


def _citizen_has_payment(db: Session, person_id: str | None) -> bool | None:
    if person_id is None:
        return None
    return db.execute(select(Case.id).where(Case.claimant_person_id == person_id, Case.status.in_(PAID_STATUSES))).first() is not None


def check(db: Session, text: str, sender: str | None, on_call: bool | None, person_id: str | None) -> ScamResult:
    text = normalise(text)
    try:
        nouls, model_id = _jev_signals(text)
        fallback = False
    except JevUnavailable:
        nouls, model_id, fallback = _keyword_signals(text), None, True
    bands = {k: noul_band(v) for k, v in nouls.items()}
    keys: list[str] = []
    risk = 1.0
    for name, weight in WEIGHTS.items():
        risk *= 1 - weight * nouls[name]
    # Genuine programmes never ask for a fee or a code, so a clear "yes" to either is strong evidence on its own.
    if bands["asks_fee"] == Band.YES:
        keys.append("asks_fee")
        risk *= STRONG_SIGNAL_FACTOR
    if bands["asks_secret"] == Band.YES:
        keys.append("asks_secret")
        risk *= STRONG_SIGNAL_FACTOR
    if LINK.search(text) and not _official_link(text):
        keys.append("unofficial_link")
        risk *= 0.85
    if sender and sender.upper() not in OFFICIAL_SENDERS and bands["claims_government"] != Band.NO:
        keys.append("unofficial_sender")
        risk *= 0.9  # sender ID is evidence, never proof (official IDs can be spoofed)
    if bands["urgency"] == Band.YES:
        keys.append("urgency")
    has_payment = _citizen_has_payment(db, person_id)
    cross = None
    if bands["claims_payment_ready"] != Band.NO and has_payment is False:
        keys.append("no_payment_pending")
        cross = "Your claim shows no payment waiting for you."
        risk *= 0.85
    if on_call:
        keys.append("on_call")
        risk *= 0.85
    score = round(1 - risk, 3)
    money_doubt = any(bands[s] == Band.UNDECIDED for s in MONEY_SIGNALS)
    if score >= 0.7:
        verdict = "LIKELY_SCAM"
    elif score <= 0.3 and not money_doubt and not fallback:
        verdict = "LOOKS_GENUINE"
    else:
        verdict = "NOT_SURE"
        keys.append("checker_not_sure")
    scam_type = "fee" if "asks_fee" in keys else "secret_code" if "asks_secret" in keys else "link" if "unofficial_link" in keys else \
        "impersonation" if "unofficial_sender" in keys else "other"
    signals = {"nouls": nouls, "fallback": fallback, "sender_official": bool(sender and sender.upper() in OFFICIAL_SENDERS), "on_call": bool(on_call)}
    return ScamResult(verdict, score, [REASONS[k][1] for k in keys], [REASONS[k][0] for k in keys], scam_type, model_id, signals, cross)


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode()).hexdigest()
