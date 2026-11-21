"""Deterministic link checks for Scam Shield. Written from scratch for this prototype.

Nothing here touches the network: a link is never opened, fetched or "unshortened"
(that would be a server-side request forgery risk and would tell the scammer the link
was clicked). A known shortener is flagged as "we cannot see where this goes".

Each link gets a list of findings (codes), all computed in code:
  lookalike             imitates an official domain (brand token, typo, homoglyph, suffix trick)
  non_latin             the host has non-Latin letters (e.g. Cyrillic "i" in "bisp")
  punycode              the host is an IDN in xn-- form
  shortener             a known URL shortener hides the real address
  raw_ip                the host is a bare IP address
  suspicious_tld        a cheap top-level domain often seen in scam campaigns
  insecure_http         plain http:// (no padlock)
  login_or_payment_path the path or query asks to log in, verify, pay or enter a code
  userinfo_trick        "official.site@other.site": the browser goes to the part after @
  odd_characters        characters no normal host has (e.g. "_" or "%"); never official
A backslash is read as "/" the way browsers do, so "evil.com\\.bisp.gov.pk" is evil.com.
An official link (allowlisted, ASCII, https or no scheme) has no lookalike finding.
"""
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from rapidfuzz.distance import Levenshtein

# Official domains. "mock" = this prototype's own invented domain. "real-world reference" =
# a real Pakistani government or payment domain, listed so that imitations of it are caught;
# the prototype never contacts these sites.
OFFICIAL_DOMAINS: dict[str, str] = {
    "pension.gov.example": "mock",
    "bisp.gov.pk": "real-world reference",
    "nadra.gov.pk": "real-world reference",
    "pta.gov.pk": "real-world reference",
    "nccia.gov.pk": "real-world reference",
    "fbr.gov.pk": "real-world reference",
    "pakistan.gov.pk": "real-world reference",
    "sbp.org.pk": "real-world reference",
    "jazzcash.com.pk": "real-world reference",
    "easypaisa.com.pk": "real-world reference",
}
# Only the government can register under gov.pk, so any ASCII *.gov.pk host counts as official.
OFFICIAL_SUFFIXES = ("gov.pk",)
SECOND_LEVEL = {"gov.pk", "com.pk", "org.pk", "net.pk", "edu.pk", "web.pk", "gob.pk", "co.uk", "org.uk", "com.au", "co.in", "gov.example"}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.ly", "cutt.ly", "rb.gy", "is.gd", "goo.gl", "ow.ly", "shorturl.at", "tiny.cc",
    "t.co", "rebrand.ly", "s.id", "v.gd", "bl.ink", "short.io", "lnkd.in", "buff.ly", "shorturl.asia",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "icu", "click", "live", "buzz", "shop", "online", "site", "cyou", "rest", "info", "monster",
    "sbs", "cfd", "quest", "lat", "vip", "work", "support", "gq", "tk", "ml", "cf", "ga", "loan", "win",
}
LOGIN_WORDS = re.compile(
    r"(log-?in|sign-?in|verif|otp|\bpin\b|password|pay|wallet|claim|kyc|update|account|secure|confirm|reward|prize|cnic)", re.I)
BARE_TLDS = ("com|net|org|pk|info|xyz|top|example|io|co|me|app|site|online|live|click|shop|icu|buzz|ly|gl|gd|at|cc|in|"
             "uk|us|ru|cn|biz|tk|ml|ga|cf|gq|vip|work|support|sbs|cfd|monster|loan|win|cyou|rest|quest|lat")
URL_PATTERN = re.compile(
    r"(?P<scheme>https?://[^\s<>\"']+)"
    r"|(?P<www>\bwww\.[^\s<>\"']+)"
    r"|(?P<ip>\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?(?:/[^\s<>\"']*)?)"
    rf"|(?P<bare>\b(?:[\w-]+\.)+(?:{BARE_TLDS})\b(?:/[^\s<>\"']*)?)",
    re.I,
)
TRAILING = ".,;:!?)]}'\"،۔"
# Letters that look like Latin ones (Cyrillic, Greek) and digit swaps used in lookalike domains.
CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "һ": "h",
    "ԁ": "d", "ɡ": "g", "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t",
    "0": "o", "1": "l", "3": "e", "5": "s", "@": "a",
})
HOST_CHARS = re.compile(r"[a-z0-9.\-\[\]:]+")  # letters, digits, dots, hyphens (and IPv6 brackets)
MIN_FUZZY_BRAND = 5  # typo distance only for brands of 5+ letters ("pension", "nadra"), never "pta"


@dataclass(frozen=True)
class LinkReport:
    url: str
    host: str
    registrable: str
    official: bool
    official_label: str | None = None  # "mock" | "real-world reference"
    imitates: str | None = None  # the official domain a lookalike seems to copy
    findings: tuple[str, ...] = field(default_factory=tuple)
    fetched: bool = False  # always False: links are never opened

    def to_dict(self) -> dict:
        return {"host": self.host, "registrable": self.registrable, "official": self.official,
                "official_label": self.official_label, "imitates": self.imitates, "findings": list(self.findings),
                "fetched": self.fetched}


@dataclass(frozen=True)
class FoundUrl:
    raw: str
    host: str
    scheme: str | None
    path: str
    userinfo: bool


def registrable_domain(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _brands() -> dict[str, str]:
    """Brand token -> official domain, e.g. "bisp" -> "bisp.gov.pk"."""
    out = {}
    for domain in OFFICIAL_DOMAINS:
        reg = registrable_domain(domain)
        out[reg.split(".")[0]] = domain
    return out


BRANDS = _brands()


def extract_urls(text: str) -> list[FoundUrl]:
    found = []
    for match in URL_PATTERN.finditer(unicodedata.normalize("NFKC", text)):
        raw = match.group(0).rstrip(TRAILING)
        scheme = raw.split("://", 1)[0].lower() if "://" in raw else None
        # Browsers read "\" as "/" in http(s) URLs, so "evil.com\.bisp.gov.pk" goes to evil.com.
        browser_form = raw.replace("\\", "/")
        parts = urlsplit(browser_form if scheme else f"http://{browser_form}")
        host = (parts.hostname or "").rstrip(".")
        if not host:
            continue
        found.append(FoundUrl(raw=raw, host=host, scheme=scheme, path=f"{parts.path}?{parts.query}", userinfo="@" in parts.netloc))
    return found


def _skeleton(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).translate(CONFUSABLES).replace("rn", "m").replace("vv", "w")


def _official(host: str) -> str | None:
    if not host.isascii() or "xn--" in host:
        return None
    reg = registrable_domain(host)
    if reg in OFFICIAL_DOMAINS:
        return OFFICIAL_DOMAINS[reg]
    if any(host == s or host.endswith(f".{s}") for s in OFFICIAL_SUFFIXES):
        return "real-world reference"
    return None


def _imitates(host: str) -> str | None:
    """Does a non-official host copy an official one? Token, typo, homoglyph and suffix tricks."""
    skeleton = _skeleton(host)
    for domain in OFFICIAL_DOMAINS:
        if domain in skeleton:  # "bisp.gov.pk.verify-now.xyz", Cyrillic "bіsp.gov.pk"
            return domain
    tokens = [t for t in re.split(r"[.\-_]", skeleton) if t]
    for token in tokens:
        if token in BRANDS:
            return BRANDS[token]
        for brand, domain in BRANDS.items():
            if len(brand) >= MIN_FUZZY_BRAND and Levenshtein.distance(token, brand) == 1:
                return domain
    return None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def analyse(url: FoundUrl) -> LinkReport:
    host = url.host.lower()
    reg = registrable_domain(host)
    label = _official(host)
    findings: list[str] = []
    imitates = None
    if not host.isascii():
        findings.append("non_latin")
    if "xn--" in host:
        findings.append("punycode")
    if host.isascii() and not HOST_CHARS.fullmatch(host):
        findings.append("odd_characters")  # e.g. "_", "%": never a normal official host
    if label is None and not _is_ip(host):
        imitates = _imitates(host)
        if imitates:
            findings.append("lookalike")
    if reg in SHORTENERS or host in SHORTENERS:
        findings.append("shortener")
    if _is_ip(host):
        findings.append("raw_ip")
    if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS:
        findings.append("suspicious_tld")
    if url.scheme == "http":
        findings.append("insecure_http")
    if label is None and LOGIN_WORDS.search(url.path):
        findings.append("login_or_payment_path")
    if url.userinfo:
        findings.append("userinfo_trick")
    official = label is not None and not url.userinfo and "odd_characters" not in findings
    return LinkReport(url=url.raw, host=host, registrable=reg, official=official, official_label=label,
                      imitates=imitates, findings=tuple(findings))


def analyse_text(text: str) -> list[LinkReport]:
    return [analyse(u) for u in extract_urls(text)]
