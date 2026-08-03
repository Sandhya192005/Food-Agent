import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Access tokens are short-lived, stateless JWTs. Refresh tokens are opaque random
# strings whose hash is stored server-side (app/models/refresh_token.py), which is
# what makes individual-token revocation on logout possible without a JWT blacklist.


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid token", code="invalid_token") from exc

    if payload.get("type") != "access":
        raise AuthError("Invalid token type", code="invalid_token_type")

    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthError("Invalid token payload", code="invalid_token") from exc


def generate_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token_value: str) -> str:
    return hashlib.sha256(token_value.encode("utf-8")).hexdigest()
