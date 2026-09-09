from pathlib import Path

from app.mail.types import EmailTemplate

TEMPLATES_DIR = Path(__file__).parent / "templates"

TEMPLATE_FILES = {
    "otp_login": "otp_login.html",
}


def render(template: EmailTemplate) -> str:
    filename = TEMPLATE_FILES[template.id]
    html = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    for key, value in template.variables.items():
        html = html.replace("{{{" + str(key) + "}}}", str(value))
    return html
