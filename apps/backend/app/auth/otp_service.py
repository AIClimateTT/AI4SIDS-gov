import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.service import issue_token_pair
from app.auth.tokens import hash_otp, hmac_compare_otp
from app.config import settings


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class OtpIssued:
    email: str
    code: str
    recipient_name: str | None = None


def _generate_code() -> str:
    length = settings.otp_length
    return f"{secrets.randbelow(10 ** length):0{length}d}"


def request_otp(db: Session, email: str) -> OtpIssued | None:
    """Return None for unknown/inactive users so the route stays enumeration-safe."""
    normalized = email.lower().strip()
    user = repo.get_by_email(db, normalized)
    repo.invalidate_unused_for_email(db, normalized)
    if user is None or not user.is_active:
        db.commit()
        return None
    code = _generate_code()
    repo.create_otp(
        db,
        email=normalized,
        code_hash=hash_otp(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.otp_ttl_minutes),
    )
    db.commit()
    return OtpIssued(email=user.email, code=code, recipient_name=user.first_name)


def verify_otp(db: Session, email: str, code: str) -> dict:
    normalized = email.lower().strip()
    row = repo.get_latest_unused(db, normalized)
    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.consumed_at is not None
        or _as_utc(row.expires_at) <= now
        or not hmac_compare_otp(code, row.code_hash)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user = repo.get_by_email(db, normalized)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    repo.mark_consumed(db, row, now)
    repo.touch_last_login(user, now)
    return issue_token_pair(db, user)
