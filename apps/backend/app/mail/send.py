from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.mail.types import SendEmailRequest
from app.mail import EmailSender


def send_email(db: Session, email_sender: EmailSender, request: SendEmailRequest) -> None:
    del db  # reserved for an email log; send stays at the adapter boundary
    try:
        email_sender.send(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please try again.",
        ) from exc
