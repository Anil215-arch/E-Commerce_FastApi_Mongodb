import jwt
from uuid import uuid4
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from app.core.config import settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def _create_token(data: dict, lifetime: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + lifetime
    to_encode.update(
        {
        "iat": now,
        "exp": expire,
        "token_type": token_type,
        "jti": str(uuid4())
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    lifetime = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data, lifetime, "access")


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    lifetime = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(data, lifetime, "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_token_expiration(payload: dict) -> datetime:
    exp = payload.get("exp")
    if exp is None:
        raise ValueError("Token payload is missing exp claim")
    return datetime.fromtimestamp(exp, tz=timezone.utc)
