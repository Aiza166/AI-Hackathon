"""PIN hashing, JWT issue/verify and API key hashing."""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "sahara-api"
JWT_AUDIENCE = "sahara-app"


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def _encode(claims: dict, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, role: str, tenant_id: str) -> str:
    minutes = get_settings().jwt_access_minutes
    # "sid": issue time in milliseconds. Logout and the PIN lockout revoke every token issued
    # before the revoking audit event. No refresh tokens: sign in again after expiry.
    claims = {"sub": user_id, "role": role, "tid": tenant_id, "typ": "access", "sid": int(time.time() * 1000)}
    return _encode(claims, timedelta(minutes=minutes))


def decode_token(token: str, expected_type: str) -> dict:
    """Verify signature, expiry, issuer, audience and algorithm. Raises jwt.InvalidTokenError."""
    claims = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )
    if claims.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return claims


def new_api_key() -> tuple[str, str, str]:
    """Return (plain_key, prefix, sha256_hash). The plain key is shown once, never stored."""
    plain = "sk_" + secrets.token_urlsafe(32)
    return plain, plain[:10], hash_api_key(plain)


def hash_api_key(plain: str) -> str:
    # High-entropy random keys: a fast hash is appropriate (no dictionary attack surface).
    return hashlib.sha256(plain.encode()).hexdigest()
