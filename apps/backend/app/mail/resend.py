from __future__ import annotations

import resend

from app.config import settings
from app.mail.renderer import render
from app.mail.types import SendEmailRequest, SendEmailResponse


class ResendEmailSender:
    def __init__(self) -> None:
        api_key = settings.resend_api_key
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is not set")
        resend.api_key = api_key
        self._default_from = settings.from_email

    def send(self, req: SendEmailRequest) -> SendEmailResponse:
        html = req.html
        if req.template is not None and not html:
            html = render(req.template)
        params: dict[str, object] = {
            "from": req.from_address or self._default_from,
            "to": req.to,
            "subject": req.subject,
        }
        if html:
            params["html"] = html
        if req.text:
            params["text"] = req.text
        resp = resend.Emails.send(params)
        return SendEmailResponse(id=str(resp.get("id", "") if isinstance(resp, dict) else ""))
