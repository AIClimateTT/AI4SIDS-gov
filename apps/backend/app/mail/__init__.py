from __future__ import annotations

from typing import Protocol

from app.config import settings
from app.mail.types import SendEmailRequest, SendEmailResponse


class EmailSender(Protocol):
    def send(self, req: SendEmailRequest) -> SendEmailResponse: ...


def get_email_sender() -> EmailSender:
    if settings.app_env.lower() in ("production", "staging"):
        from app.mail.resend import ResendEmailSender

        return ResendEmailSender()
    from app.mail.mailpit import MailpitEmailSender

    return MailpitEmailSender()
