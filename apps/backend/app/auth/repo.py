from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import LoginOtp, RefreshToken, User

WORKSPACE_ROLES = ("dmu", "admin")
MANAGED_ROLES = ("dmu", "admin", "corp")


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: str | UUID) -> User | None:
    uid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    return db.get(User, uid)


def get_active_by_id(db: Session, user_id: str | UUID) -> User | None:
    user = get_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    return user


def list_workspace_users(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role.in_(MANAGED_ROLES)).order_by(User.email)
        ).all()
    )


def touch_last_login(user: User, now: datetime) -> None:
    user.last_login = now


def invalidate_unused_for_email(db: Session, email: str) -> None:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(LoginOtp).where(
            LoginOtp.email == email,
            LoginOtp.consumed_at.is_(None),
        )
    ).all()
    for row in rows:
        row.consumed_at = now


def create_otp(
    db: Session,
    *,
    email: str,
    code_hash: str,
    expires_at: datetime,
) -> LoginOtp:
    row = LoginOtp(email=email, code_hash=code_hash, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def get_latest_unused(db: Session, email: str) -> LoginOtp | None:
    return db.scalar(
        select(LoginOtp)
        .where(LoginOtp.email == email, LoginOtp.consumed_at.is_(None))
        .order_by(LoginOtp.created_at.desc())
    )


def mark_consumed(db: Session, row: LoginOtp, now: datetime) -> None:
    row.consumed_at = now


def get_refresh_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def revoke_all_for_user(db: Session, user_id: UUID, now: datetime | None = None) -> None:
    when = now or datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = when


def delete_refresh_tokens_for_user(db: Session, user_id: UUID) -> None:
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
