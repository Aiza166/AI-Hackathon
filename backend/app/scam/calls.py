"""Caller and sender checks for Scam Shield. Written from scratch for this prototype.

A number or sender ID is **evidence, never proof**: official short codes can be masked
(BISP 8171 spoofing was reported, PID PR No. 59, 5 Jul 2024), and scammers use SIMs
registered to other people. So a match with an official code never makes a message
"genuine" by itself; it only removes the "unofficial sender" signal. An official SMS
short code or a helpline *calling you* is itself a red flag: those numbers send messages
or take calls, they do not ring citizens to ask for codes or fees.
"""
import re
from dataclasses import dataclass, field

# Normalised sender -> (label, what it is). "mock" entries are this prototype's invented senders.
OFFICIAL_CALLERS: dict[str, tuple[str, str]] = {
    "PENSION-GOV": ("mock", "sms_sender"),
    "08000000000": ("mock", "helpline"),  # mock pension helpline 0800-00000-00
    "8171": ("real-world reference", "sms_sender"),  # BISP official SMS short code
    "080026477": ("real-world reference", "helpline"),  # BISP helpline 0800-26477
}
SPOOF_NOTE = "spoofable"  # always attached to an official match
HIDDEN_WORDS = ("private", "unknown", "hidden", "no caller id", "نامعلوم")
PK_MOBILE = re.compile(r"^03\d{9}$")
NUMBER_IN_TEXT = re.compile(r"(?<!\d)(?:\+?92[\s-]?|0)3\d{2}[\s-]?\d{7}(?!\d)|(?<!\d)\+\d[\d\s-]{7,16}\d(?!\d)")


@dataclass(frozen=True)
class CallerReport:
    raw: str | None
    normalised: str | None
    channel: str
    official_label: str | None = None
    official_kind: str | None = None
    findings: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        # The number itself is not returned or stored: only what kind of number it is.
        return {"channel": self.channel, "official_label": self.official_label, "official_kind": self.official_kind,
                "findings": list(self.findings), "notes": list(self.notes)}


def normalise_number(raw: str) -> str:
    text = raw.strip()
    if re.search(r"[A-Za-z]", text):
        return text.upper().replace(" ", "")
    digits = re.sub(r"\D", "", text)
    if digits.startswith("0092"):
        digits = "0" + digits[4:]
    elif text.startswith("+92") or (digits.startswith("92") and len(digits) == 12):
        digits = "0" + digits[2:]
    elif text.startswith("+") or digits.startswith("00"):
        return "+" + digits.lstrip("0")
    return digits


def analyse_caller(raw: str | None, channel: str = "sms") -> CallerReport:
    is_call = channel == "call"
    if raw is None or not raw.strip() or any(w in raw.lower() for w in HIDDEN_WORDS):
        return CallerReport(raw, None, channel, findings=("hidden_number",) if is_call else ())
    number = normalise_number(raw)
    findings: list[str] = []
    notes: list[str] = []
    label, kind = OFFICIAL_CALLERS.get(number, (None, None))
    if label:
        notes.append(SPOOF_NOTE)
        if is_call and kind == "sms_sender":
            findings.append("official_code_calling")
        elif is_call and kind == "helpline":
            findings.append("helpline_calling_you")
    elif number.startswith("+"):
        findings.append("international")
    elif PK_MOBILE.match(number):
        findings.append("personal_mobile")
    return CallerReport(raw, number, channel, label, kind, tuple(findings), tuple(notes))


def find_number(text: str) -> str | None:
    """First phone number in OCR text (a chat header usually shows the sender's number)."""
    match = NUMBER_IN_TEXT.search(text)
    return match.group(0).strip() if match else None
