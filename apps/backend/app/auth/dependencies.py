from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.models import User
from app.auth.tokens import decode_access_token
from app.db import get_session

_bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = repo.get_active_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_dmu_user(current_user: CurrentUser) -> User:
    if current_user.role != "dmu":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DMU role required",
        )
    return current_user


DmuUser = Annotated[User, Depends(require_dmu_user)]
