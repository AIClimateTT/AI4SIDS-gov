from pathlib import Path

import pytest

from app.core.registry import reset_registry
from app.db import engine as db_engine
from app.auth.passwords import hash_password
from tests.auth_helpers import FakeEmailSender, create_user, make_auth_client

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_state():
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    reset_registry()
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


OTP_DETAIL = "If an account exists for that email, a code has been sent."


def test_otp_request_unknown_email_is_enumeration_safe():
    client, sender = make_auth_client()

    response = client.post("/auth/otp/request", json={"email": "nobody@example.com"})

    assert response.status_code == 202
    assert response.json() == {"detail": OTP_DETAIL}
    assert sender.sent == []


def test_otp_request_inactive_user_does_not_send():
    create_user(is_active=False)
    client, sender = make_auth_client()

    response = client.post("/auth/otp/request", json={"email": "ada@example.com"})

    assert response.status_code == 202
    assert response.json() == {"detail": OTP_DETAIL}
    assert sender.sent == []


def test_otp_request_existing_user_sends_code_and_never_returns_it():
    create_user()
    client, sender = make_auth_client()

    response = client.post("/auth/otp/request", json={"email": "ada@example.com"})

    assert response.status_code == 202
    assert response.json() == {"detail": OTP_DETAIL}
    assert "code" not in response.json()
    assert len(sender.sent) == 1
    code = sender.sent[0].template.variables["VERIFICATION_CODE"]
    assert isinstance(code, str) and len(code) == 6 and code.isdigit()
    assert code in sender.sent[0].text


def test_otp_send_failure_returns_503():
    create_user()
    sender = FakeEmailSender(fail=True)
    client, _ = make_auth_client(sender)

    response = client.post("/auth/otp/request", json={"email": "ada@example.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Failed to send verification email. Please try again."


def test_otp_verify_issues_token_pair():
    create_user()
    client, sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})
    code = sender.sent[0].template.variables["VERIFICATION_CODE"]

    response = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": code}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_otp_verify_wrong_code_is_generic_400():
    create_user()
    client, _sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})

    response = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": "000000"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification code"


def test_me_requires_bearer_and_returns_user():
    create_user()
    client, sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})
    code = sender.sent[0].template.variables["VERIFICATION_CODE"]
    tokens = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": code}
    ).json()

    denied = client.get("/auth/me")
    assert denied.status_code == 401

    ok = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["email"] == "ada@example.com"
    assert body["role"] == "dmu"
    assert body["first_name"] == "Ada"


def test_refresh_rotates_and_reuse_revokes_all():
    create_user()
    client, sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})
    code = sender.sent[0].template.variables["VERIFICATION_CODE"]
    first = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": code}
    ).json()

    rotated = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]

    reused = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reused.status_code == 401

    follow = client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert follow.status_code == 401


def test_logout_revokes_refresh_token():
    create_user()
    client, sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})
    code = sender.sent[0].template.variables["VERIFICATION_CODE"]
    tokens = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": code}
    ).json()

    out = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 200
    assert out.json() == {"detail": "Logged out"}

    again = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_otp_resend_invalidates_previous_code():
    create_user()
    client, sender = make_auth_client()
    client.post("/auth/otp/request", json={"email": "ada@example.com"})
    first_code = sender.sent[0].template.variables["VERIFICATION_CODE"]
    client.post("/auth/otp/resend", json={"email": "ada@example.com"})
    second_code = sender.sent[1].template.variables["VERIFICATION_CODE"]

    stale = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": first_code}
    )
    assert stale.status_code == 400

    fresh = client.post(
        "/auth/otp/verify", json={"email": "ada@example.com", "code": second_code}
    )
    assert fresh.status_code == 200


LOGIN_DETAIL = "Invalid email or password"


def test_password_login_issues_token_pair_and_me():
    create_user(password_hash=hash_password("secret123"))
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "secret123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["role"] == "dmu"


@pytest.mark.parametrize(
    "role,email,corporation",
    [
        ("dmu", "officer@example.com", None),
        ("admin", "admin@example.com", None),
        ("corp", "corp@example.com", "diego_martin_regional_corporati"),
    ],
)
def test_password_login_works_for_each_role(role: str, email: str, corporation: str | None):
    create_user(
        email=email,
        role=role,
        corporation=corporation,
        password_hash=hash_password("secret123"),
    )
    client, _ = make_auth_client()

    response = client.post("/auth/login", json={"email": email, "password": "secret123"})

    assert response.status_code == 200
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert me.json()["role"] == role


def test_password_login_wrong_password_is_generic_401():
    create_user(password_hash=hash_password("secret123"))
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrongpass"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_DETAIL


def test_password_login_unknown_email_is_generic_401():
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "secret123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_DETAIL


def test_password_login_inactive_user_is_generic_401():
    create_user(is_active=False, password_hash=hash_password("secret123"))
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "secret123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_DETAIL


def test_password_login_missing_hash_is_generic_401():
    create_user()
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "secret123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_DETAIL
