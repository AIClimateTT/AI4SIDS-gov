from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.models import RefreshToken, User
from app.auth.passwords import hash_password, verify_with_timing_protection
from app.auth.tokens import create_access_token
from app.db import Base, SessionLocal, engine as db_engine
from app.api.users import router as users_router

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"


@pytest.fixture(autouse=True)
def _clean_state():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    Base.metadata.create_all(db_engine)
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(users_router)
    return app


def _create_user(**kwargs) -> User:
    session = SessionLocal()
    user = User(
        email=kwargs.get("email", "ada@example.com"),
        role=kwargs.get("role", "dmu"),
        first_name=kwargs.get("first_name", "Ada"),
        last_name=kwargs.get("last_name"),
        corporation=kwargs.get("corporation"),
        is_active=kwargs.get("is_active", True),
        password_hash=kwargs.get("password_hash"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user


def _token(user: User) -> str:
    return create_access_token(
        user_id=user.user_id,
        role=user.role,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        corporation=user.corporation,
    )


def _client(user: User | None = None) -> TestClient:
    client = TestClient(_app())
    if user is not None:
        client.headers["Authorization"] = f"Bearer {_token(user)}"
    return client


def test_unauthenticated_list_is_401():
    response = _client().get("/users")
    assert response.status_code == 401


def test_corp_user_cannot_list_users():
    corp = _create_user(
        email="corp@example.com",
        role="corp",
        corporation="diego_martin_regional_corporati",
    )
    response = _client(corp).get("/users")
    assert response.status_code == 403


def test_officer_cannot_list_or_create_users():
    officer = _create_user(role="dmu")
    client = _client(officer)

    listed = client.get("/users")
    assert listed.status_code == 403

    created = client.post(
        "/users",
        json={
            "email": "sam@example.com",
            "first_name": "Sam",
            "password": "secret123",
        },
    )
    assert created.status_code == 403


def test_admin_can_create_and_list_dmu_admin_and_corp_users():
    actor = _create_user(role="admin")
    _create_user(
        email="existing-corp@example.com",
        role="corp",
        corporation="diego_martin_regional_corporati",
    )
    client = _client(actor)

    created = client.post(
        "/users",
        json={
            "email": "Sam@Example.com",
            "first_name": "Sam",
            "last_name": "Lee",
            "password": "secret123",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "sam@example.com"
    assert body["role"] == "dmu"
    assert body["is_active"] is True
    assert body["has_password"] is True
    assert body["corporation"] is None
    assert "password" not in body
    assert "password_hash" not in body

    admin_created = client.post(
        "/users",
        json={
            "email": "boss@example.com",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert admin_created.status_code == 201
    assert admin_created.json()["role"] == "admin"
    assert admin_created.json()["corporation"] is None

    listed = client.get("/users")
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()}
    assert emails == {
        "ada@example.com",
        "sam@example.com",
        "boss@example.com",
        "existing-corp@example.com",
    }


def test_admin_can_create_and_update_corp_users():
    actor = _create_user(role="admin")
    client = _client(actor)

    created = client.post(
        "/users",
        json={
            "email": "clerk@arima.gov.tt",
            "password": "secret123",
            "role": "corp",
            "corporation": "arima_borough_corporation",
            "first_name": "Pat",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["role"] == "corp"
    assert body["corporation"] == "arima_borough_corporation"
    assert body["first_name"] == "Pat"

    updated = client.patch(
        f"/users/{body['user_id']}",
        json={
            "first_name": "Patricia",
            "corporation": "siparia_regional_corporation",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Patricia"
    assert updated.json()["corporation"] == "siparia_regional_corporation"


def test_changing_corporation_revokes_refresh_tokens():
    actor = _create_user(role="admin")
    target = _create_user(
        email="clerk@arima.gov.tt",
        role="corp",
        corporation="arima_borough_corporation",
    )
    session = SessionLocal()
    session.add(
        RefreshToken(
            user_id=target.user_id,
            token_hash="c" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    session.commit()
    session.close()

    response = _client(actor).patch(
        f"/users/{target.user_id}",
        json={"corporation": "siparia_regional_corporation"},
    )
    assert response.status_code == 200

    session = SessionLocal()
    row = session.query(RefreshToken).one()
    assert row.revoked_at is not None
    session.close()


def test_create_corp_user_requires_a_canonical_corporation():
    actor = _create_user(role="admin")
    client = _client(actor)

    missing = client.post(
        "/users",
        json={
            "email": "clerk@example.com",
            "password": "secret123",
            "role": "corp",
        },
    )
    assert missing.status_code == 422

    unknown = client.post(
        "/users",
        json={
            "email": "clerk@example.com",
            "password": "secret123",
            "role": "corp",
            "corporation": "not_a_corporation",
        },
    )
    assert unknown.status_code == 400
    assert "corporation" in unknown.json()["detail"]


def test_two_corp_users_may_share_a_corporation():
    actor = _create_user(role="admin")
    client = _client(actor)
    payload = {
        "password": "secret123",
        "role": "corp",
        "corporation": "arima_borough_corporation",
    }

    first = client.post("/users", json={**payload, "email": "one@arima.gov.tt"})
    second = client.post("/users", json={**payload, "email": "two@arima.gov.tt"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["corporation"] == second.json()["corporation"]


def test_create_officer_ignores_corporation():
    actor = _create_user(role="admin")
    created = _client(actor).post(
        "/users",
        json={
            "email": "officer@example.com",
            "password": "secret123",
            "role": "dmu",
            "corporation": "arima_borough_corporation",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == "dmu"
    assert created.json()["corporation"] is None


def test_create_user_without_password_is_422():
    actor = _create_user(role="admin")
    response = _client(actor).post("/users", json={"email": "sam@example.com"})
    assert response.status_code == 422


def test_duplicate_email_is_409():
    actor = _create_user(role="admin")
    response = _client(actor).post(
        "/users", json={"email": "ada@example.com", "password": "secret123"}
    )
    assert response.status_code == 409


def test_update_user_name_and_email():
    actor = _create_user(role="admin")
    target = _create_user(email="sam@example.com", first_name="Sam")
    response = _client(actor).patch(
        f"/users/{target.user_id}",
        json={"first_name": "Samantha", "email": "samantha@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Samantha"
    assert response.json()["email"] == "samantha@example.com"


def test_cannot_set_corporation_on_an_officer():
    actor = _create_user(role="admin")
    officer = _create_user(email="sam@example.com", role="dmu")
    response = _client(actor).patch(
        f"/users/{officer.user_id}",
        json={"corporation": "arima_borough_corporation"},
    )
    assert response.status_code == 400
    assert "corporation" in response.json()["detail"]


def test_cannot_deactivate_or_delete_self():
    actor = _create_user(role="admin")
    client = _client(actor)

    deactivated = client.post(f"/users/{actor.user_id}/deactivate")
    assert deactivated.status_code == 409

    deleted = client.delete(f"/users/{actor.user_id}")
    assert deleted.status_code == 409


def test_deactivate_revokes_refresh_tokens_and_delete_removes_row():
    actor = _create_user(role="admin")
    target = _create_user(email="sam@example.com")
    session = SessionLocal()
    session.add(
        RefreshToken(
            user_id=target.user_id,
            token_hash="a" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    session.commit()
    session.close()

    client = _client(actor)
    deactivated = client.post(f"/users/{target.user_id}/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    session = SessionLocal()
    row = session.query(RefreshToken).one()
    assert row.revoked_at is not None
    session.close()

    activated = client.post(f"/users/{target.user_id}/activate")
    assert activated.json()["is_active"] is True

    deleted = client.delete(f"/users/{target.user_id}")
    assert deleted.status_code == 204
    listed = client.get("/users").json()
    assert listed == [
        {
            "user_id": str(actor.user_id),
            "email": actor.email,
            "first_name": actor.first_name,
            "last_name": actor.last_name,
            "role": "admin",
            "corporation": None,
            "is_active": True,
            "last_login": None,
            "has_password": False,
        }
    ]


def test_officer_cannot_set_password():
    officer = _create_user(role="dmu")
    target = _create_user(email="sam@example.com")
    response = _client(officer).post(
        f"/users/{target.user_id}/set-password",
        json={"password": "newsecret"},
    )
    assert response.status_code == 403


def test_set_password_hashes_and_revokes_refresh_tokens():
    actor = _create_user(role="admin")
    target = _create_user(email="sam@example.com")
    session = SessionLocal()
    session.add(
        RefreshToken(
            user_id=target.user_id,
            token_hash="b" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    session.commit()
    session.close()

    response = _client(actor).post(
        f"/users/{target.user_id}/set-password",
        json={"password": "newsecret"},
    )
    assert response.status_code == 200
    assert response.json()["has_password"] is True
    assert "password" not in response.json()

    session = SessionLocal()
    user = session.get(User, target.user_id)
    assert user is not None
    assert verify_with_timing_protection("newsecret", user.password_hash)
    row = session.query(RefreshToken).one()
    assert row.revoked_at is not None
    session.close()


def test_admin_can_set_own_password():
    actor = _create_user(role="admin")
    response = _client(actor).post(
        f"/users/{actor.user_id}/set-password",
        json={"password": "newsecret"},
    )
    assert response.status_code == 200
    assert response.json()["has_password"] is True
