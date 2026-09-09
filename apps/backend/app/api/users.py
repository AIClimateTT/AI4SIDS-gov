from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field

from app.auth.dependencies import AdminUser, SessionDep
from app.auth.models import User
from app.auth import users_service

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    user_id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    is_active: bool
    last_login: datetime | None
    has_password: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str | None = None
    last_name: str | None = None
    role: Literal["dmu", "admin"] = "dmu"


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None


class SetPasswordBody(BaseModel):
    password: str = Field(min_length=8)


def _to_out(user: User) -> UserOut:
    return UserOut(
        user_id=user.user_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login,
        has_password=user.password_hash is not None,
    )


@router.get("", response_model=list[UserOut])
def list_users(db: SessionDep, _actor: AdminUser) -> list[UserOut]:
    return [_to_out(user) for user in users_service.list_users(db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: SessionDep, _actor: AdminUser) -> UserOut:
    return _to_out(
        users_service.create_user(
            db,
            email=body.email,
            first_name=body.first_name,
            last_name=body.last_name,
            password=body.password,
            role=body.role,
        )
    )


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID, body: UserUpdate, db: SessionDep, _actor: AdminUser
) -> UserOut:
    return _to_out(
        users_service.update_user(
            db,
            user_id,
            email=body.email,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    )


@router.post("/{user_id}/set-password", response_model=UserOut)
def set_password(
    user_id: UUID, body: SetPasswordBody, db: SessionDep, _actor: AdminUser
) -> UserOut:
    return _to_out(users_service.set_password(db, user_id, body.password))


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: UUID, db: SessionDep, actor: AdminUser) -> UserOut:
    return _to_out(users_service.set_active(db, actor, user_id, True))


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: UUID, db: SessionDep, actor: AdminUser) -> UserOut:
    return _to_out(users_service.set_active(db, actor, user_id, False))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: SessionDep, actor: AdminUser) -> None:
    users_service.delete_user(db, actor, user_id)
