"""Shared rate limiter (slowapi).

Key: the signed-in user's id when the request carries a valid access token, otherwise
the client IP. The client IP is the right-most X-Forwarded-For entry that is not one
of our trusted proxies (FORWARDED_ALLOW_IPS), so a client cannot pick its own IP by
sending a fake header. Storage: Redis in production (shared by all workers and
restarts), process memory elsewhere.
"""
import ipaddress
import logging

import jwt
from slowapi import Limiter
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import decode_token

log = logging.getLogger("sahara.ratelimit")
Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_trusted(value: str) -> tuple[Network, ...]:
    networks = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            log.warning("Ignoring invalid FORWARDED_ALLOW_IPS entry")
    return tuple(networks)


_trusted = _parse_trusted(get_settings().forwarded_allow_ips)


def _is_trusted(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _trusted)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted(peer):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in reversed([h.strip() for h in forwarded.split(",") if h.strip()]):
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            return peer  # malformed chain: do not guess
        if not _is_trusted(hop):
            return hop
    return peer


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return "user:" + decode_token(auth[7:].strip(), expected_type="access")["sub"]
        except jwt.InvalidTokenError:
            pass
    return "ip:" + client_ip(request)


def _storage_uri() -> str:
    settings = get_settings()
    if settings.ratelimit_storage_uri:
        return settings.ratelimit_storage_uri
    if settings.is_production and settings.redis_url:
        try:
            import redis  # noqa: F401  (limits needs the client library for redis:// storage)
        except ImportError:
            log.warning("redis package missing: rate limits fall back to process memory")
            return "memory://"
        return settings.redis_url
    return "memory://"


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["300/minute"],
    storage_uri=_storage_uri(),
    in_memory_fallback_enabled=True,  # Redis down: keep limiting per process rather than failing open
    key_prefix="sahara-rl",
)
