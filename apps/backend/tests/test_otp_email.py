from app.auth.notifications import build_otp_login_email
from app.mail.renderer import render


def test_otp_email_renders_code_and_plain_text():
    request = build_otp_login_email(
        to_email="ada@example.com",
        verification_code="123456",
        recipient_name="Ada",
    )

    assert "123456" in request.text
    assert request.template is not None
    html = render(request.template)
    assert "123456" in html
    assert "Ada" in html
    assert "ada@example.com" in html
    assert "{{{VERIFICATION_CODE}}}" not in html
