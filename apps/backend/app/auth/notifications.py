from app.config import settings
from app.mail.types import EmailTemplate, SendEmailRequest


def build_otp_login_email(
    *,
    to_email: str,
    verification_code: str,
    recipient_name: str | None = None,
) -> SendEmailRequest:
    name = recipient_name or "there"
    ttl = settings.otp_ttl_minutes
    text = (
        f"Dear {name},\n\n"
        f"Your sign-in code is {verification_code}.\n\n"
        f"This code expires in {ttl} minutes. If you did not request it, ignore this email."
    )
    return SendEmailRequest(
        to=[to_email],
        subject="Your sign-in code",
        text=text,
        template=EmailTemplate(
            id="otp_login",
            variables={
                "NAME": name,
                "USER_EMAIL": to_email,
                "VERIFICATION_CODE": verification_code,
                "EXPIRY_MINUTES": str(ttl),
                "APP_NAME": settings.app_name,
                "LOGO_URL": settings.email_logo_url,
                "SUPPORT_EMAIL": settings.support_email,
                "BRAND_COLOR": settings.brand_color,
            },
        ),
    )
