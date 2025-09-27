import hashlib
import time
import uuid

import jwt

from src.config import settings


def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password


def _base_claims(subject: str, ttl_seconds: int, *, token_type: str, extra: dict) -> dict:
    now = int(time.time())
    return {
        "sub": subject,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": token_type,
        **extra,
    }


def create_access_token(user: dict) -> tuple[str, int]:
    """user = {'id': int, 'username': str}"""
    ttl = settings.access_token_expire_minutes * 60
    payload = _base_claims(str(user["id"]), ttl, token_type="access", extra=user)

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def create_refresh_token(user: dict) -> tuple[str, int]:
    ttl = settings.refresh_token_expire_days * 24 * 60 * 60
    payload = _base_claims(str(user["id"]), ttl, token_type="refresh", extra=user)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "nbf", "aud", "iss", "jti", "type"]},
    )
