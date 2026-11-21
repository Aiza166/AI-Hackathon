"""Judge-console shortcuts (demo reset, mock faults, skipping the payout hold).

Outside production they are open to the platform admin. In production they also need
the X-Demo-Console-Token header to match DEMO_CONSOLE_TOKEN (constant-time compare).
With no token configured they are switched off. Either way the caller sees a plain
404, so the console does not advertise itself.
"""
import hmac

from fastapi import HTTPException, Request

from app.core.config import get_settings

HEADER = "X-Demo-Console-Token"


def console_allowed(request: Request) -> bool:
    settings = get_settings()
    if not settings.is_production:
        return True
    expected = settings.demo_console_token
    if not expected:
        return False
    given = request.headers.get(HEADER, "")
    return hmac.compare_digest(given.encode(), expected.encode())


def require_console(request: Request) -> None:
    if not console_allowed(request):
        raise HTTPException(status_code=404, detail="Not Found")
