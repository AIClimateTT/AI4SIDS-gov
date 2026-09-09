from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import RefreshToken, User
from app.auth import repo
from app.auth.tokens import create_access_token
from app.config import settings


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_refresh_token_row(db: Session, user_id: UUID) -> tuple[str, RefreshToken]:
    raw = RefreshToken.generate_raw()
    row = RefreshToken(
        user_id=user_id,
        token_hash=RefreshToken.hash_token(raw),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(row)
    db.flush()
    return raw, row


def issue_token_pair(db: Session, user: User) -> dict:
    access = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    raw_refresh, _row = create_refresh_token_row(db, user.user_id)
    db.commit()
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


def refresh_token_pair(db: Session, raw_refresh: str) -> dict:
    token_hash = RefreshToken.hash_token(raw_refresh)
    row = repo.get_refresh_by_hash(db, token_hash)
    now = datetime.now(timezone.utc)
    if row is None or _as_utc(row.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if row.revoked_at is not None:
        repo.revoke_all_for_user(db, row.user_id, now)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = repo.get_active_by_id(db, row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    row.revoked_at = now
    new_raw, new_row = create_refresh_token_row(db, user.user_id)
    row.replaced_by_id = new_row.id
    db.commit()
    access = create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )
    return {
        "access_token": access,
        "refresh_token": new_raw,
        "token_type": "bearer",
    }


def logout_refresh_token(db: Session, raw_refresh: str) -> None:
    token_hash = RefreshToken.hash_token(raw_refresh)
    row = repo.get_refresh_by_hash(db, token_hash)
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
