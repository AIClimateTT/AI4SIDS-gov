from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from app import create_app
from app.auth.models import User
from app.db import Base, engine as db_engine, SessionLocal
from app.mail import get_email_sender
from app.mail.types import SendEmailRequest, SendEmailResponse


@dataclass
class FakeEmailSender:
    sent: list[SendEmailRequest] = field(default_factory=list)
    fail: bool = False

    def send(self, req: SendEmailRequest) -> SendEmailResponse:
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(req)
        return SendEmailResponse(id="fake")


def make_auth_client(sender: FakeEmailSender | None = None) -> tuple[TestClient, FakeEmailSender]:
    Base.metadata.create_all(db_engine)
    fake = sender or FakeEmailSender()
    app = create_app()
    app.dependency_overrides[get_email_sender] = lambda: fake
    return TestClient(app), fake


def create_user(
    *,
    email: str = "ada@example.com",
    role: str = "dmu",
    first_name: str = "Ada",
    is_active: bool = True,
    corporation: str | None = None,
    password_hash: str | None = None,
) -> User:
    Base.metadata.create_all(db_engine)
    session = SessionLocal()
    user = User(
        email=email,
        role=role,
        first_name=first_name,
        is_active=is_active,
        corporation=corporation,
        password_hash=password_hash,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user
