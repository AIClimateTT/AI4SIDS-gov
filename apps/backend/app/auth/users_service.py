from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.models import User
from app.auth.passwords import hash_password
from app.auth.repo import WORKSPACE_ROLES


def _normalize_email(email: str) -> str:
    return email.lower().strip()


def list_users(db: Session) -> list[User]:
    return repo.list_workspace_users(db)


def get_managed_user(db: Session, user_id: UUID) -> User:
    user = repo.get_by_id(db, user_id)
    if user is None or user.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def create_user(
    db: Session,
    *,
    email: str,
    first_name: str | None,
    last_name: str | None,
    password: str,
    role: str = "dmu",
) -> User:
    normalized = _normalize_email(email)
    if repo.get_by_email(db, normalized) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )
    user = User(
        email=normalized,
        first_name=first_name.strip() if first_name else None,
        last_name=last_name.strip() if last_name else None,
        role=role,
        corporation=None,
        is_active=True,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: UUID,
    *,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
) -> User:
    user = get_managed_user(db, user_id)
    if email is not None:
        normalized = _normalize_email(email)
        existing = repo.get_by_email(db, normalized)
        if existing is not None and existing.user_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with that email already exists",
            )
        user.email = normalized
    if first_name is not None:
        user.first_name = first_name.strip() or None
    if last_name is not None:
        user.last_name = last_name.strip() or None
    db.commit()
    db.refresh(user)
    return user


def _reject_self(actor: User, target: User, action: str) -> None:
    if actor.user_id == target.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You cannot {action} your own account",
        )


def set_active(db: Session, actor: User, user_id: UUID, is_active: bool) -> User:
    user = get_managed_user(db, user_id)
    if not is_active:
        _reject_self(actor, user, "deactivate")
        repo.revoke_all_for_user(db, user.user_id)
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, actor: User, user_id: UUID) -> None:
    user = get_managed_user(db, user_id)
    _reject_self(actor, user, "delete")
    repo.revoke_all_for_user(db, user.user_id)
    repo.delete_refresh_tokens_for_user(db, user.user_id)
    db.delete(user)
    db.commit()


def set_password(db: Session, user_id: UUID, password: str) -> User:
    user = get_managed_user(db, user_id)
    user.password_hash = hash_password(password)
    repo.revoke_all_for_user(db, user.user_id)
    db.commit()
    db.refresh(user)
    return user
