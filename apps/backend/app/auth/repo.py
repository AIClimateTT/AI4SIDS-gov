from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import RefreshToken, User


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


def list_dmu_users(db: Session) -> list[User]:
    return list(
        db.scalars(select(User).where(User.role == "dmu").order_by(User.email)).all()
    )


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
