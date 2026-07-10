import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return str(bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())


def verify_password(plain: str, hashed: str) -> bool:
    return bool(bcrypt.checkpw(plain.encode(), hashed.encode()))


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return str(jwt.encode(payload, settings.secret_key, algorithm="HS256"))


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub: str | None = payload.get("sub")
        return sub
    except JWTError:
        return None


def new_oauth_token() -> str:
    return secrets.token_urlsafe(48)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)
