"""Error monitoring with Sentry, scrubbed so no personal data leaves the server.

Off unless SENTRY_DSN is set. Every event, transaction and breadcrumb goes through `scrub_event`
/ `scrub_breadcrumb` before it is sent:
- request bodies and cookies are dropped entirely; the user block is emptied
- secret-looking keys anywhere (pin, password, token, authorization, api key, cookie, secret,
  refresh, otp, iban, cnic, phone) are replaced with "[Filtered]"
- every remaining string is masked: CNIC and IBAN (shared helper in core/redact.py), phone
  numbers, PINs written as "pin 1234", JWTs, bearer tokens and our `sk_` API keys
- query strings keep their keys but sensitive values are filtered and the rest masked
"""
import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode

from app.core.redact import redact_text

FILTERED = "[Filtered]"
TRACES_SAMPLE_RATE = 0.1
MAX_DEPTH = 12
SENSITIVE_KEY_PARTS = (
    "pin", "password", "passwd", "secret", "token", "authorization", "auth", "cookie", "api_key", "apikey",
    "api-key", "x-api-key", "session", "refresh", "otp", "iban", "cnic", "phone", "idempotency", "dsn",
)
# Sentry bookkeeping fields: never rewrite them (ids and timestamps are long digit runs).
_KEEP_KEYS = {"event_id", "trace_id", "span_id", "parent_span_id", "timestamp", "start_timestamp", "release",
              "sdk", "platform", "level", "lineno", "colno", "type"}

_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_API_KEY = re.compile(r"\bsk_[A-Za-z0-9_-]{8,}")
_PIN = re.compile(r"(?i)\b(pin|password|passcode|otp)(\W{1,4})(\d{4,8})\b")
# 10-15 digits, optional leading + and dashes or spaces inside: Pakistani mobiles (03xx-xxxxxxx,
# +92 3xx xxxxxxx) and the 11-digit demo phones. CNICs and IBANs are masked before this runs.
_PHONE = re.compile(r"(?<![\w*])(\+?\d(?:[ -]?\d){9,14})(?![\w*])")

# What the SDK itself may collect: no user identity, cookies, bodies, SQL values or frame locals.
DATA_COLLECTION = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "denylist", "terms": ["cookie", "x-api-key", "idempotency"]}},
    "http_bodies": [],
    "url_query_params": {"mode": "denylist", "terms": ["cnic", "iban", "phone", "pin"]},
    "database_query_data": False,
    "stack_frame_variables": False,
}

_enabled = False


def _mask_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(1))
    return "*" * (len(digits) - 2) + digits[-2:]


def scrub_text(value: str) -> str:
    """Mask every personal identifier and credential we know in free text."""
    value = _JWT.sub("[token]", value)
    value = _BEARER.sub(lambda m: f"{m.group(1)} {FILTERED}", value)
    value = _API_KEY.sub("[api-key]", value)
    value = _PIN.sub(lambda m: f"{m.group(1)}{m.group(2)}****", value)
    value = redact_text(value)  # CNIC + IBAN, shared with the audit trail and log filter
    return _PHONE.sub(_mask_phone, value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def scrub(value: Any, depth: int = 0) -> Any:
    """Return a scrubbed copy (dicts, lists, strings). Never mutates the input."""
    if depth > MAX_DEPTH:
        return FILTERED
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {k: _scrub_item(k, v, depth) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], str) and _is_sensitive_key(value[0]):
            return [value[0], FILTERED]  # header pairs: ["Authorization", "Bearer ..."]
        return [scrub(v, depth + 1) for v in value]
    return value


def _scrub_item(key: Any, value: Any, depth: int) -> Any:
    if not isinstance(key, str):
        return scrub(value, depth + 1)
    if key in _KEEP_KEYS:
        return value
    if _is_sensitive_key(key) and value not in (None, "", [], {}):
        return FILTERED
    return scrub(value, depth + 1)


def scrub_query_string(query: str | None) -> str | None:
    if not query:
        return query
    pairs = [(k, FILTERED if _is_sensitive_key(k) else scrub_text(v)) for k, v in parse_qsl(query, keep_blank_values=True)]
    return urlencode(pairs, safe="*[]")


def _scrub_request(request: dict) -> dict:
    kept = {k: v for k, v in request.items() if k not in ("data", "cookies", "env")}
    if isinstance(kept.get("query_string"), str):
        kept["query_string"] = scrub_query_string(kept["query_string"])
    if isinstance(kept.get("url"), str):
        base, _, query = kept["url"].partition("?")
        kept["url"] = scrub_text(base) + (f"?{scrub_query_string(query)}" if query else "")
    return scrub(kept)


def scrub_event(event: dict, _hint: dict | None = None) -> dict:
    """Sentry before_send / before_send_transaction hook."""
    cleaned = {k: v for k, v in event.items() if k not in ("request", "user")}
    cleaned = scrub(cleaned)
    if isinstance(event.get("request"), dict):
        cleaned["request"] = _scrub_request(event["request"])
    user = event.get("user")
    role = user.get("role") if isinstance(user, dict) else None
    cleaned["user"] = {"role": role} if isinstance(role, str) else {}
    return cleaned


def scrub_breadcrumb(crumb: dict, _hint: dict | None = None) -> dict:
    """Sentry before_breadcrumb hook: masks message and data, drops any captured body."""
    data = crumb.get("data")
    cleaned = {k: v for k, v in crumb.items() if k != "data"}
    cleaned = scrub(cleaned)
    if isinstance(data, dict):
        body_free = {k: v for k, v in data.items() if k not in ("body", "request_body", "response_body")}
        if isinstance(body_free.get("url"), str):
            base, _, query = body_free["url"].partition("?")
            body_free["url"] = scrub_text(base) + (f"?{scrub_query_string(query)}" if query else "")
        cleaned["data"] = scrub(body_free)
    return cleaned


def sentry_environment(configured: str) -> str:
    """SENTRY_ENVIRONMENT wins; on Railway default to production; otherwise the app environment."""
    explicit = os.environ.get("SENTRY_ENVIRONMENT", "").strip()
    if explicit:
        return explicit
    if os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_PROJECT_ID"):
        return "production"
    return configured or "local"


def sentry_release() -> str | None:
    sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "").strip()
    return f"sahara-backend@{sha[:12]}" if sha else None


def is_enabled() -> bool:
    return _enabled


def init_sentry(dsn: str | None, environment: str) -> bool:
    """Start Sentry if a DSN is set. Returns whether it is on. Never logs the DSN."""
    global _enabled
    if not dsn:
        _enabled = False
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=sentry_environment(environment),
        release=sentry_release(),
        data_collection=DATA_COLLECTION,  # replaces send_default_pii=False in sentry-sdk >= 2.75
        traces_sample_rate=TRACES_SAMPLE_RATE,
        before_send=scrub_event,
        before_send_transaction=scrub_event,
        before_breadcrumb=scrub_breadcrumb,
    )
    _enabled = True
    return True
