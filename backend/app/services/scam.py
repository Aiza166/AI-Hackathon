"""Scam Shield: is this "your pension is released, pay a fee" message a scam?

Two sensors, code decides. Jev answers small factual questions about the message; normalised
keyword and link rules run on every check as a floor (never only when Jev is down). When the two
disagree, or Jev looks steered by text aimed at it, the answer is NOT_SURE, never a green light.
Content signals (fee, secret code, link) outweigh the sender ID, the citizen's real case is
cross-checked, and a message is never called genuine on one sensor alone. Reasons shown to
people are fixed text, never generated.
"""
import hashlib
import hmac
import logging
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision.jev_client import Band, JevClient, JevUnavailable, noul, noul_band, valid_probability
from app.models.platform import Case
from app.services import textnorm

log = logging.getLogger("sahara.scam")

# Sender IDs and domains are weak evidence only: SMS sender IDs can be spoofed.
OFFICIAL_SENDERS = {"PENSION-GOV", "8171"}  # mock official sender for this prototype; 8171 is BISP's real SMS short code
OFFICIAL_DOMAINS = ("pension.gov.example", "bisp.gov.pk")  # mock official domain + BISP's real domain
SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "ow.ly", "shorturl.at", "tiny.cc",
              "rebrand.ly", "s.id", "v.gd", "bitly.com", "tny.im", "short.gy")
CHAT_LINKS = ("wa.me", "t.me", "chat.whatsapp.com", "api.whatsapp.com", "telegram.me", "m.me")

# Word-bounded lexicons run on normalised text (English, Roman Urdu, Urdu script).
NEGATED_FEE = re.compile(
    r"\b(?:no|without any|without|zero)\s+(?:fee|fees|charges?)(?:\s+(?:is|are|will be))?(?:\s+charged)?\b|\bfree of (?:charge|cost)\b|"
    r"\bkoi (?:fee|fees|charges?) nahi\b|\b(?:fee|fees) nahi\b|کوئی فیس نہیں|فیس نہیں",
)
NEGATED_SECRET = re.compile(
    r"\b(?:never|do not|don't|dont|na|mat)\s+(?:share|give|tell|batayen|bataen|dein)\s+(?:your\s+|apna\s+)?(?:otp|pin|password|code)\b"
    r"|\b(?:otp|pin|code|password)\s+(?:kisi ko\s+)?(?:na|mat)\s+(?:batayen|bataen|dein|bataein)\b|اپنا کوڈ کسی کو نہ",
)
FEE_WORDS = re.compile(
    r"\b(?:fee|fees|charges?|processing charges?|pay\s*rs|rupay|rupees?|rs\.?\s*\d+|pkr\s*\d+|send\s*rs|paisay|paise|paisa|pesay|"
    r"rakam|raqam|jama|bhej\w*|transfer\s+(?:rs|money|amount)|easypaisa|easy paisa|jazzcash|jazz cash|deposit|tax|token money)\b"
    r"|روپے|فیس|رقم|جمع|پیسے|بھیج",
)
SECRET_WORDS = re.compile(
    r"\b(?:otp|pin|pin code|password|passcode|code|verification|cvv|mpin|tpin|kod)\b|کوڈ|او ٹی پی|پن کوڈ|پاس ورڈ|\bپن\b",
)
GOV_WORDS = re.compile(
    r"\b(?:bisp|benazir|ehsaas|government|govt|hukumat|sarkar|sarkari|pension|ministry|nadra|relief|imdad|programme|program)\b"
    r"|حکومت|سرکاری|پنشن|بینظیر|احساس|امداد|نادرا",
)
PAYMENT_READY = re.compile(
    r"\b(?:released|ready|approved|credited|disbursed|jari|mil gay[ie]|aa gay[ie]|qist|installment|payment)\b|جاری|منظور|قسط|ادائیگی",
)
URGENCY_WORDS = re.compile(r"\b(?:today|within \d+|urgent|immediately|cancel\w*|block\w*|last chance|jaldi|fori|aaj hi)\b|فوری|آج ہی|جلدی")
INJECTION_WORDS = re.compile(
    r"\b(?:ignore (?:all|any|the|previous|above)|disregard|system\s*:|assistant\s*:|you are an? (?:ai|model|checker|classifier)|"
    r"(?:ai|automated) (?:checker|system|classifier)|answer (?:no|yes) to|noul|mark (?:this|it|as) (?:safe|genuine)|"
    r"looks_genuine|not a scam|this is (?:safe|genuine|not a scam)|checker)\b",
)
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
KEYWORD_FLOOR = 0.6  # a keyword match alone is mid-band (undecided): it can never be ignored, nor is it proof
KEYWORD_CONFIRMED = 0.75  # keyword match plus a second red flag in the same message
INJECTION_LIMIT = 0.3  # Jev's "aimed at a checker" above this means the message may be steering the checker
LINK_PAYMENT_FLOOR = 0.4  # unofficial link + payment/government claim: never green
SPLIT_FLOOR = 0.7  # fee/code in one message and a link in another within 24 h
SHORTENER_FACTOR = 0.6
GENUINE_MAX = 0.3
SCAM_MIN = 0.7

GENUINE_CAVEAT = ("ہمیں کوئی خطرے کی علامت نہیں ملی، لیکن ہم تصدیق نہیں کر سکتے کہ یہ اصلی ہے۔",
                  "We found no warning signs, but we cannot confirm this is real.")
REASONS = {
    "asks_fee": ("پیسے یا فیس مانگی گئی ہے۔ حکومت کبھی فیس نہیں مانگتی۔", "It asks for money or a fee. The government never charges a fee."),
    "asks_secret": ("کوڈ یا پن مانگا گیا ہے۔ اپنا کوڈ کسی کو نہ دیں۔", "It asks for a code or PIN. Never share your code."),
    "unofficial_link": ("اس میں غیر سرکاری لنک ہے۔ اسے نہ کھولیں۔", "It has a link that is not an official website. Do not open it."),
    "short_link": ("اس میں چھپا ہوا یا چیٹ والا لنک ہے۔ اسے نہ کھولیں۔", "It has a shortened or chat link that hides where it goes. Do not open it."),
    "unofficial_sender": ("یہ سرکاری نمبر سے نہیں آیا۔ نمبر جعلی بھی ہو سکتا ہے۔",
                          "It did not come from the official sender. Sender names can also be faked."),
    "urgency": ("یہ جلدی یا دھمکی سے دباؤ ڈالتا ہے۔", "It pressures you with a deadline or threat."),
    "no_payment_pending": ("آپ کے دعوے میں کوئی ادائیگی باقی نہیں۔", "Your claim shows no payment waiting for you."),
    "on_call": ("کوئی فون پر آپ کو یہ کرنے کو کہہ رہا ہے۔ فون بند کریں۔", "Someone on the phone is telling you to do this. Hang up."),
    "steering_text": ("اس پیغام میں چیک کرنے والے نظام کے لیے ہدایات ہیں۔", "The message contains text aimed at fooling our checker."),
    "split_message": ("پچھلے پیغام کے ساتھ مل کر یہ فیس اور لنک والا دھوکہ لگتا ہے۔",
                      "Together with an earlier message, this looks like a fee-and-link scam."),
    "checker_not_sure": ("ہمیں یقین نہیں۔ کسی مددگار یا افسر سے پوچھیں۔", "We are not sure. Ask a helper or an officer."),
    "looks_genuine": GENUINE_CAVEAT,
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


@dataclass(frozen=True)
class KeywordSignals:
    fee: bool
    secret: bool
    gov: bool
    payment_ready: bool
    urgency: bool
    injection: bool
    links: tuple[str, ...]

    @property
    def money(self) -> bool:
        return self.fee or self.secret


@dataclass(frozen=True)
class LinkFindings:
    any_link: bool
    unofficial: bool
    short_or_chat: bool


# ---------------------------------------------------------------- per-user limits and memory


class PerUserQuota:
    """In-memory sliding-window counter keyed on a user id (not IP). Per process; fine for one instance."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


SPLIT_WINDOW_SECONDS = 24 * 3600


class SplitMemory:
    """Remembers, per user, salted hashes of recent messages and whether each had a fee/code or a link.

    Only HMAC digests and two booleans are kept (never text), for 24 hours, in memory.
    """

    def __init__(self, window_seconds: float = SPLIT_WINDOW_SECONDS, max_per_user: int = 50):
        self.window = window_seconds
        self.max_per_user = max_per_user
        self._items: dict[str, deque[tuple[float, str, bool, bool]]] = defaultdict(deque)
        self._lock = threading.Lock()

    def remember_and_check(self, user_key: str, digest: str, money: bool, link: bool, now: float | None = None) -> bool:
        """True when this message plus an earlier, different one together hold both a fee/code and a link."""
        now = time.time() if now is None else now
        with self._lock:
            items = self._items[user_key]
            while items and items[0][0] <= now - self.window:
                items.popleft()
            earlier = [i for i in items if i[1] != digest]
            split = (money and any(i[3] for i in earlier)) or (link and any(i[2] for i in earlier))
            items.append((now, digest, money, link))
            while len(items) > self.max_per_user:
                items.popleft()
            return split

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


split_memory = SplitMemory()


# ---------------------------------------------------------------- canary circuit breaker

CANARY_TEXT = ("BISP: your Benazir payment of Rs 25000 is released. Pay Rs 1500 processing fee on easypaisa and send the "
               "OTP you receive to claim it today: http://bisp-release.example.com/claim")
BREAKER_SECONDS = 30 * 60


class CanaryBreaker:
    """Trips when Jev clears a known scam; while tripped no check may come back LOOKS_GENUINE."""

    def __init__(self) -> None:
        self._until = 0.0
        self._lock = threading.Lock()

    def trip(self, seconds: float = BREAKER_SECONDS) -> None:
        with self._lock:
            self._until = time.time() + seconds
        log.warning("Scam Shield canary failed: Jev cleared a known scam; forcing NOT_SURE for %d s", int(seconds))

    def active(self) -> bool:
        with self._lock:
            return time.time() < self._until

    def reset(self) -> None:
        with self._lock:
            self._until = 0.0


breaker = CanaryBreaker()


def jev_only_verdict(nouls: dict[str, float]) -> str:
    """What Jev alone would conclude (no keyword floor). Used only by the canary."""
    bands = {k: noul_band(v) for k, v in nouls.items()}
    risk = 1.0
    for name, weight in WEIGHTS.items():
        risk *= 1 - weight * nouls[name]
    for name in MONEY_SIGNALS:
        if bands[name] == Band.YES:
            risk *= STRONG_SIGNAL_FACTOR
    score = 1 - risk
    if score >= SCAM_MIN:
        return "LIKELY_SCAM"
    if score <= GENUINE_MAX and not any(bands[s] == Band.UNDECIDED for s in MONEY_SIGNALS):
        return "LOOKS_GENUINE"
    return "NOT_SURE"


def run_canary() -> dict:
    """Send a known scam through the Jev path. If Jev calls it genuine (or misses the fee), trip the breaker."""
    try:
        nouls, model_id = _jev_signals(textnorm.clean(CANARY_TEXT))
    except JevUnavailable:
        return {"status": "jev_unavailable", "tripped": False, "breaker_active": breaker.active()}
    verdict = jev_only_verdict(nouls)
    failed = verdict == "LOOKS_GENUINE" or noul_band(nouls["asks_fee"]) == Band.NO
    if failed:
        breaker.trip()
    return {"status": "failed" if failed else "passed", "jev_verdict": verdict, "model_id": model_id,
            "tripped": failed, "breaker_active": breaker.active()}


# ---------------------------------------------------------------- signals


def normalise(text: str) -> str:
    """Kept for callers and the stored hash: NFKC without hidden characters."""
    return textnorm.clean(text)


def _jev_signals(text: str) -> tuple[dict[str, float], str | None]:
    client = JevClient()
    try:
        result = client.ask({"untrusted_message": text}, QUESTIONS)  # labelled: the message is data, not instructions
        try:
            return {name: valid_probability(result.noul(name)) for name in QUESTIONS}, result.model
        except (KeyError, TypeError, ValueError) as exc:
            raise JevUnavailable(f"Jev answer was not usable: {type(exc).__name__}") from exc
    finally:
        client.close()


def _keywords_in(text: str) -> KeywordSignals:
    fee_text = NEGATED_FEE.sub(" ", text)
    secret_text = NEGATED_SECRET.sub(" ", text)
    return KeywordSignals(
        fee=bool(FEE_WORDS.search(fee_text)), secret=bool(SECRET_WORDS.search(secret_text)), gov=bool(GOV_WORDS.search(text)),
        payment_ready=bool(PAYMENT_READY.search(text)), urgency=bool(URGENCY_WORDS.search(text)),
        injection=bool(INJECTION_WORDS.search(text)), links=tuple(textnorm.extract_links(text)),
    )


def keyword_signals(text: str) -> KeywordSignals:
    """Score both the raw (lowercased) and the normalised text and keep every hit: the higher risk wins."""
    raw, norm = _keywords_in(textnorm.clean(text).lower()), _keywords_in(textnorm.for_matching(text))
    return KeywordSignals(
        fee=raw.fee or norm.fee, secret=raw.secret or norm.secret, gov=raw.gov or norm.gov,
        payment_ready=raw.payment_ready or norm.payment_ready, urgency=raw.urgency or norm.urgency,
        injection=raw.injection or norm.injection, links=tuple(dict.fromkeys(raw.links + norm.links)),
    )


def _keyword_nouls(kw: KeywordSignals) -> dict[str, float]:
    """Fallback when Jev is unavailable: deliberately cautious mid-band values, so a match is never treated as certain."""
    return {"asks_fee": KEYWORD_FLOOR if kw.fee else 0.1, "asks_secret": KEYWORD_FLOOR if kw.secret else 0.1,
            "has_link": 0.9 if kw.links else 0.05, "urgency": 0.5 if kw.urgency else 0.1,
            "claims_government": 0.8 if kw.gov else 0.5, "claims_payment_ready": 0.8 if kw.payment_ready else 0.5,
            "addresses_reader_instructions": 0.8 if kw.injection else 0.1}


def link_findings(links: tuple[str, ...]) -> LinkFindings:
    hosts = [textnorm.host_of(link) for link in links]
    unofficial = any(not textnorm.host_matches(h, OFFICIAL_DOMAINS) for h in hosts)
    short = any(textnorm.host_matches(h, SHORTENERS + CHAT_LINKS) for h in hosts)
    return LinkFindings(bool(links), unofficial, short)


def _official_link(text: str) -> bool:
    found = link_findings(tuple(textnorm.extract_links(text)))
    return found.any_link and not found.unofficial


def _citizen_has_payment(db: Session | None, person_id: str | None) -> bool | None:
    if db is None or person_id is None:
        return None
    return db.execute(select(Case.id).where(Case.claimant_person_id == person_id, Case.status.in_(PAID_STATUSES))).first() is not None


def _floored(nouls: dict[str, float], kw: KeywordSignals, links: LinkFindings) -> dict[str, float]:
    """Keyword sensor as a floor under Jev: a match can raise a Noul, never lower it."""
    second_flag = links.unofficial or kw.gov or kw.payment_ready or kw.urgency
    money_floor = KEYWORD_CONFIRMED if second_flag else KEYWORD_FLOOR
    floors = {"asks_fee": money_floor if kw.fee else 0.0, "asks_secret": money_floor if kw.secret else 0.0,
              "has_link": 0.9 if links.any_link else 0.0, "urgency": 0.5 if kw.urgency else 0.0,
              "claims_government": 0.75 if kw.gov else 0.0, "claims_payment_ready": 0.75 if kw.payment_ready else 0.0,
              "addresses_reader_instructions": 0.75 if kw.injection else 0.0}
    return {k: max(v, floors.get(k, 0.0)) for k, v in nouls.items()}


def _disagree(jev: dict[str, float], kw: KeywordSignals, links: LinkFindings) -> bool:
    """Keyword sensor sees a fee, code or link that Jev says is clearly not there."""
    pairs = (("asks_fee", kw.fee), ("asks_secret", kw.secret), ("has_link", links.any_link))
    return any(seen and noul_band(jev[name]) == Band.NO for name, seen in pairs)


def check(db: Session | None, text: str, sender: str | None, on_call: bool | None, person_id: str | None,
          *, use_jev: bool = True, user_key: str | None = None, secret: str | None = None) -> ScamResult:
    """use_jev=False forces the keyword fallback (used by the offline evaluation).
    user_key + secret enable split-message memory (HMAC of the normalised text, 24 h)."""
    cleaned = textnorm.clean(text)
    kw = keyword_signals(text)
    links = link_findings(kw.links)
    try:
        if not use_jev:
            raise JevUnavailable("Jev disabled for this check")
        jev_nouls, model_id = _jev_signals(cleaned)
        fallback = False
    except JevUnavailable:
        jev_nouls, model_id, fallback = _keyword_nouls(kw), None, True
    nouls = _floored(jev_nouls, kw, links)
    bands = {k: noul_band(v) for k, v in nouls.items()}
    disagreement = not fallback and _disagree(jev_nouls, kw, links)
    steering = kw.injection or jev_nouls["addresses_reader_instructions"] > INJECTION_LIMIT

    keys: list[str] = []
    risk = 1.0
    for name, weight in WEIGHTS.items():
        risk *= 1 - weight * nouls[name]
    # Genuine programmes never ask for a fee or a code, so a clear "yes" to either is strong evidence on its own.
    for name in MONEY_SIGNALS:
        if bands[name] == Band.YES:
            keys.append(name)
            risk *= STRONG_SIGNAL_FACTOR
    if links.unofficial:
        keys.append("unofficial_link")
        risk *= 0.85
    if links.short_or_chat:
        keys.append("short_link")
        risk *= SHORTENER_FACTOR
    sender_official = bool(sender and sender.strip().upper() in OFFICIAL_SENDERS)
    gov_claim = bands["claims_government"] != Band.NO
    if sender and not sender_official and gov_claim:
        keys.append("unofficial_sender")
        risk *= 0.9  # sender ID is evidence, never proof (official IDs can be spoofed)
    if bands["urgency"] == Band.YES:
        keys.append("urgency")
    has_payment = _citizen_has_payment(db, person_id)
    cross = None
    payment_claim = bands["claims_payment_ready"] != Band.NO
    if payment_claim and has_payment is False:
        keys.append("no_payment_pending")
        cross = "Your claim shows no payment waiting for you."
        risk *= 0.85
    if on_call:
        keys.append("on_call")
        risk *= 0.85
    score = 1 - risk

    if links.unofficial and (payment_claim or gov_claim):
        score = max(score, LINK_PAYMENT_FLOOR)
    if steering:
        keys.append("steering_text")
        if kw.money or any(bands[s] != Band.NO for s in MONEY_SIGNALS):
            score = max(score, SCAM_MIN)
    split = False
    if user_key and secret:
        digest = hmac.new(secret.encode(), textnorm.for_matching(text).encode(), hashlib.sha256).hexdigest()
        split = split_memory.remember_and_check(user_key, digest, kw.money or bands["asks_fee"] == Band.YES
                                                or bands["asks_secret"] == Band.YES, links.any_link)
        if split:
            keys.append("split_message")
            score = max(score, SPLIT_FLOOR)
    score = round(score, 3)

    money_doubt = any(bands[s] == Band.UNDECIDED for s in MONEY_SIGNALS)
    # A green answer needs both sensors to agree and nothing that a scam typically carries.
    risky_content = links.any_link or ((payment_claim or gov_claim or kw.gov or kw.payment_ready) and not sender_official)
    breaker_on = breaker.active()
    if score >= SCAM_MIN:
        verdict = "LIKELY_SCAM"
    elif (score <= GENUINE_MAX and not money_doubt and not fallback and not disagreement and not steering
          and not risky_content and not breaker_on):
        verdict = "LOOKS_GENUINE"
        keys.append("looks_genuine")
    else:
        verdict = "NOT_SURE"
        keys.append("checker_not_sure")
    scam_type = "fee" if "asks_fee" in keys else "secret_code" if "asks_secret" in keys else \
        "link" if ("unofficial_link" in keys or "short_link" in keys) else "impersonation" if "unofficial_sender" in keys else "other"
    signals = {"nouls": nouls, "jev_nouls": jev_nouls, "fallback": fallback, "sender_official": sender_official,
               "on_call": bool(on_call), "disagreement": disagreement, "steering": steering, "split_message": split,
               "breaker_active": breaker_on,
               "keywords": {"fee": kw.fee, "secret": kw.secret, "gov": kw.gov, "payment_ready": kw.payment_ready,
                            "links": len(kw.links), "unofficial_link": links.unofficial, "short_link": links.short_or_chat}}
    return ScamResult(verdict, score, [REASONS[k][1] for k in keys], [REASONS[k][0] for k in keys], scam_type, model_id, signals, cross)


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode()).hexdigest()
