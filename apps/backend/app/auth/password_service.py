from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.passwords import verify_with_timing_protection
from app.auth.service import issue_token_pair

LOGIN_DETAIL = "Invalid email or password"


def login_with_password(db: Session, email: str, password: str) -> dict:
    normalized = email.lower().strip()
    user = repo.get_by_email(db, normalized)
    hashed = None if user is None else user.password_hash
    if not verify_with_timing_protection(password, hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOGIN_DETAIL,
        )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOGIN_DETAIL,
        )

    repo.touch_last_login(user, datetime.now(timezone.utc))
    return issue_token_pair(db, user)
