"""PIN hashing, JWT issue/verify and API key hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "sahara-api"
JWT_AUDIENCE = "sahara-app"
REFRESH_TOKEN_DAYS = 2


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def _encode(claims: dict, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def new_jti() -> str:
    return secrets.token_hex(16)


def create_access_token(user_id: str, role: str, tenant_id: str, sid: str) -> str:
    """sid ties the token to a sign-in session, so sign-out revokes it immediately."""
    minutes = get_settings().jwt_access_minutes
    claims = {"sub": user_id, "role": role, "tid": tenant_id, "sid": sid, "jti": new_jti(), "typ": "access"}
    return _encode(claims, timedelta(minutes=minutes))


def create_refresh_token(user_id: str, sid: str, jti: str) -> str:
    """Single use: the server stores the current jti per session and rotates it on every refresh."""
    return _encode({"sub": user_id, "sid": sid, "jti": jti, "typ": "refresh"}, timedelta(days=REFRESH_TOKEN_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    """Verify signature, expiry, issuer, audience and algorithm. Raises jwt.InvalidTokenError."""
    claims = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "typ", "sid", "jti"]},
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
