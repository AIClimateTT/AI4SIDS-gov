from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.notifications import build_otp_login_email
from app.auth import otp_service, service
from app.mail import EmailSender, get_email_sender
from app.mail.send import send_email

router = APIRouter(prefix="/auth", tags=["auth"])

EmailSenderDep = Annotated[EmailSender, Depends(get_email_sender)]

OTP_REQUEST_DETAIL = "If an account exists for that email, a code has been sent."


class OtpRequestBody(BaseModel):
    email: EmailStr


class OtpVerifyBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class RefreshBody(BaseModel):
    refresh_token: str


class LogoutBody(BaseModel):
    refresh_token: str


class CurrentUserResponse(BaseModel):
    user_id: UUID
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    corporation: str | None
    is_active: bool


@router.post("/otp/request", status_code=202)
def otp_request(
    body: OtpRequestBody, db: SessionDep, email_sender: EmailSenderDep
) -> dict:
    issued = otp_service.request_otp(db, body.email)
    if issued is not None:
        send_email(
            db,
            email_sender,
            build_otp_login_email(
                to_email=issued.email,
                verification_code=issued.code,
                recipient_name=issued.recipient_name,
            ),
        )
    return {"detail": OTP_REQUEST_DETAIL}


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyBody, db: SessionDep) -> dict:
    return otp_service.verify_otp(db, body.email, body.code)


@router.post("/otp/resend", status_code=202)
def otp_resend(
    body: OtpRequestBody, db: SessionDep, email_sender: EmailSenderDep
) -> dict:
    issued = otp_service.request_otp(db, body.email)
    if issued is not None:
        send_email(
            db,
            email_sender,
            build_otp_login_email(
                to_email=issued.email,
                verification_code=issued.code,
                recipient_name=issued.recipient_name,
            ),
        )
    return {"detail": OTP_REQUEST_DETAIL}


@router.post("/refresh")
def refresh(body: RefreshBody, db: SessionDep) -> dict:
    return service.refresh_token_pair(db, body.refresh_token)


@router.post("/logout")
def logout(body: LogoutBody, db: SessionDep) -> dict:
    service.logout_refresh_token(db, body.refresh_token)
    return {"detail": "Logged out"}


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        corporation=current_user.corporation,
        is_active=current_user.is_active,
    )
