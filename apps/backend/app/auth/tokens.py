import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
OTP_TTL_MINUTES = 10
PASSWORD_RESET_TTL_MINUTES = 30


def create_access_token(
    *,
    user_id: UUID,
    role: str,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    corporation: str | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "principal_type": "user",
        "role": role,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "corporation": corporation,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def hash_otp(code: str) -> str:
    return hmac.new(settings.secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()


def hmac_compare_otp(code: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), expected_hash)


def create_password_reset_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
    payload = {"sub": str(user_id), "type": "password_reset", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Token is not a password reset token")
    return payload["sub"]
