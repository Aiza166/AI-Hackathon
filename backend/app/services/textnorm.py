"""Text normalisation and link extraction for Scam Shield.

Scammers dodge keyword checks with lookalike letters, hidden characters, spaced letters
("O T P"), Urdu digits and obfuscated links ("hxxp://evil[.]com"). Everything here turns
such text into one plain form so the keyword rules see what a person would read.
"""
import re
import unicodedata
from urllib.parse import urlsplit

# Cyrillic and Greek letters that look like Latin ones (small hand table; no library needed).
CONFUSABLES = str.maketrans({
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c",
    "т": "t", "у": "y", "х": "x", "ѕ": "s", "і": "i", "ї": "i", "ј": "j", "ԁ": "d", "д": "d", "ԛ": "q", "ԝ": "w",
    "ɡ": "g", "һ": "h", "ӏ": "l", "ո": "n", "ս": "u",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "ω": "w", "μ": "u", "ς": "c",
})
# Arabic-Indic (U+0660..) and Extended Arabic-Indic / Urdu (U+06F0..) digits to ASCII.
DIGITS = str.maketrans({**{chr(0x0660 + i): str(i) for i in range(10)}, **{chr(0x06F0 + i): str(i) for i in range(10)}})
# Runs of 2+ single Latin letters split by spaces, dots, dashes or stars: "O T P", "O.T.P", "P-I-N".
SINGLE_LETTER_RUN = re.compile(r"(?<![a-z0-9])[a-z](?:[\s.\-_*]+[a-z](?![a-z0-9]))+")

DOT_OBFUSCATIONS = re.compile(r"\s*(?:\[\s*(?:\.|dot)\s*\]|\(\s*(?:\.|dot)\s*\)|\{\s*(?:\.|dot)\s*\}|\s+dot\s+)\s*", re.I)
ODD_DOTS = re.compile("[。．｡․‧・·]")
SPACED_DOT = re.compile(r"(?<=[a-z0-9])\s+\.\s*(?=[a-z0-9])|(?<=[a-z0-9])\.\s+(?=(?:com|net|org|pk|me|ly|gl|io|co|info|xyz)\b)", re.I)
HXXP = re.compile(r"\bh[x*]{2}p(s?)\b", re.I)
# Top-level domains accepted for bare "name.tld" tokens (keeps "today.Pay" from looking like a link).
TLDS = ("com", "net", "org", "pk", "info", "xyz", "example", "io", "me", "ly", "gl", "co", "biz", "online", "site", "top",
        "club", "live", "app", "link", "click", "gov", "edu", "in", "uk", "us", "tk", "ml", "ga", "cf", "gq", "ru", "cn",
        "ws", "cc", "tv", "at", "gd", "gy", "shop", "store", "page", "cloud", "win", "vip", "icu", "pw", "su")
URL_TOKEN = re.compile(
    r"(?:(?:https?|ftp)://[^\s<>\"']+)|(?:www\.[^\s<>\"']+)|"
    r"(?:\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + "|".join(TLDS) + r")\b(?:[/:?#][^\s<>\"']*)?)",
    re.I,
)


def clean(text: str) -> str:
    """NFKC, then drop invisible format characters (zero-width etc.)."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _join_letter_runs(text: str) -> str:
    return SINGLE_LETTER_RUN.sub(lambda m: re.sub(r"[\s.\-_*]+", "", m.group(0)), text)


def for_matching(text: str) -> str:
    """The form keyword rules run on: clean, no combining marks, lookalikes folded, ASCII digits,
    lowercase, single-letter runs joined, whitespace collapsed."""
    text = unicodedata.normalize("NFKD", clean(text))
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Mn", "Me", "Cf"))
    text = unicodedata.normalize("NFKC", text).translate(CONFUSABLES).translate(DIGITS).lower()
    text = _join_letter_runs(text)
    return " ".join(text.split())


def deobfuscate_links(text: str) -> str:
    text = ODD_DOTS.sub(".", for_matching(text))
    text = HXXP.sub(lambda m: "http" + m.group(1), text)
    text = DOT_OBFUSCATIONS.sub(".", text)
    return SPACED_DOT.sub(".", text)


def extract_links(text: str) -> list[str]:
    """Every URL-like token, after undoing common obfuscation."""
    return [m.group(0).rstrip(".,;:!?)]}'\"") for m in URL_TOKEN.finditer(deobfuscate_links(text))]


def host_of(link: str) -> str | None:
    candidate = link if re.match(r"^[a-z][a-z0-9+.-]*://", link, re.I) else f"http://{link}"
    try:
        host = urlsplit(candidate).hostname
    except ValueError:
        return None
    return host.rstrip(".").lower() if host else None


def host_matches(host: str | None, domains: tuple[str, ...]) -> bool:
    """Exact host or a real subdomain: 'a.bisp.gov.pk' matches, 'bisp.gov.pk.evil.com' does not."""
    return bool(host) and any(host == d or host.endswith("." + d) for d in domains)
