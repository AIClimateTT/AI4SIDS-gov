from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.mail.renderer import render
from app.mail.types import SendEmailRequest, SendEmailResponse


def _split_from_address(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "<" in raw and raw.endswith(">"):
        name, rest = raw[:-1].split("<", 1)
        return rest.strip(), name.strip().strip('"')
    return raw, ""


class MailpitEmailSender:
    def __init__(self) -> None:
        self._url = settings.mailpit_url.rstrip("/")
        self._default_from = settings.from_email

    def send(self, req: SendEmailRequest) -> SendEmailResponse:
        html = req.html
        if req.template is not None and not html:
            html = render(req.template)
        from_email, from_name = _split_from_address(req.from_address or self._default_from)
        payload = {
            "From": {"Email": from_email, "Name": from_name},
            "To": [{"Email": address} for address in req.to],
            "Subject": req.subject,
        }
        if html:
            payload["HTML"] = html
        if req.text:
            payload["Text"] = req.text
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self._url}/api/v1/send",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Failed to send email via Mailpit") from exc
        return SendEmailResponse(id=str(data.get("ID") or data.get("id") or ""))
