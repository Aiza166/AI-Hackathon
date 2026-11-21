"""Mask personal identifiers before they reach logs or the audit trail.

CNICs (13 digits, with or without dashes) and IBANs keep only their last 4 characters.
Used by audit.record() (resource + details), access-denied paths and the uvicorn access log.
"""
import logging
import re
from typing import Any

_NOT_ALNUM_BEFORE = r"(?<![0-9A-Za-z])"
_NOT_ALNUM_AFTER = r"(?![0-9A-Za-z])"
_CNIC = re.compile(_NOT_ALNUM_BEFORE + r"(\d{5}-?\d{7}-?\d)" + _NOT_ALNUM_AFTER)
_IBAN = re.compile(_NOT_ALNUM_BEFORE + r"([A-Z]{2}\d{2}[A-Z0-9]{10,30})" + _NOT_ALNUM_AFTER)
MAX_DEPTH = 6


def _mask(match: re.Match) -> str:
    value = match.group(1)
    return "*" * (len(value) - 4) + value[-4:]


def redact_text(value: str) -> str:
    return _IBAN.sub(_mask, _CNIC.sub(_mask, value))


def redact(value: Any, depth: int = 0) -> Any:
    """Return a copy with every string (also inside dicts/lists) masked. Never mutates the input."""
    if depth > MAX_DEPTH:  # never return deep values unmasked: flatten them to masked text
        return redact_text(str(value))
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, depth + 1) for v in value]
    return value


class RedactingFilter(logging.Filter):
    """Masks CNICs/IBANs in log records: message, %-args (tuple or dict) and the traceback text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact_text(v) if isinstance(v, str) else v for k, v in record.args.items()}
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.exc_info and not record.exc_text:
            record.exc_text = redact_text(_TRACEBACKS.formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


_TRACEBACKS = logging.Formatter()
_LOGGERS = ("", "uvicorn", "uvicorn.access", "uvicorn.error", "sahara")


def install_log_redaction() -> None:
    """Attach the filter to the handlers (so records from child loggers such as sahara.speech are
    covered too) and to the named loggers (for handlers added later)."""
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        for target in (logger, *logger.handlers):
            if not any(isinstance(f, RedactingFilter) for f in target.filters):
                target.addFilter(RedactingFilter())
