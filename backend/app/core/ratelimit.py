"""Shared rate limiter (slowapi). Limits are per client IP.

Behind Railway's proxy uvicorn runs with --proxy-headers --forwarded-allow-ips '*', which puts
the LEFTMOST X-Forwarded-For entry into request.client: a value the caller chooses. So the key
is taken from the right instead: RATE_LIMIT_PROXY_HOPS = number of proxies in front of the app
that append to X-Forwarded-For (1 on Railway, 0 locally = use the socket peer address).
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

DEFAULT_LIMIT = "300/minute"


def client_ip(request: Request) -> str:
    hops = get_settings().rate_limit_proxy_hops
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-min(hops, len(parts))]
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip, default_limits=[DEFAULT_LIMIT])
