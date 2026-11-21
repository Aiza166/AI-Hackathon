"""Simulated AI-provider outages for the judge console (fallback demo).

An admin can make Jev, the second sensor, Azure OCR or Azure speech behave as if
they were down, to show the fallbacks live: Scam Shield keyword fallback, Tesseract
OCR, the phone's own voice. Each switch turns itself off after OUTAGE_MINUTES so a
forgotten toggle cannot break the demo for the next judge.

State lives in this process only (the API runs one uvicorn worker). A restart clears
it, which is the safe direction. The clients check `is_down()` before any network call;
nothing about the real provider (key, endpoint) is read or returned here.
"""
import threading
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

TARGETS = ("jev", "second_sensor", "azure_ocr", "azure_speech")
OUTAGE_MINUTES = 15

_lock = threading.Lock()
_until: MappingProxyType = MappingProxyType({})  # target -> expiry (UTC); replaced, never mutated


def _now() -> datetime:
    return datetime.now(timezone.utc)


def set_outage(target: str, down: bool, minutes: int = OUTAGE_MINUTES) -> datetime | None:
    """Switch a simulated outage on (returns its expiry) or off (returns None)."""
    global _until
    if target not in TARGETS:
        raise ValueError(f"unknown target {target}")
    with _lock:
        current = dict(_until)
        if down:
            current[target] = _now() + timedelta(minutes=minutes)
        else:
            current.pop(target, None)
        _until = MappingProxyType(current)
        return current.get(target)


def is_down(target: str) -> bool:
    expiry = _until.get(target)
    return expiry is not None and expiry > _now()


def status() -> dict[str, dict]:
    now = _now()
    snapshot = _until
    out = {}
    for target in TARGETS:
        expiry = snapshot.get(target)
        active = expiry is not None and expiry > now
        out[target] = {"simulated_down": active, "expires_at": expiry.isoformat(timespec="seconds") if active else None}
    return out


def clear_all() -> None:
    """Tests and demo reset: every provider back to normal."""
    global _until
    with _lock:
        _until = MappingProxyType({})
