from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.models import RefreshToken, User
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


def test_dmu_can_create_and_list_dmu_users_only():
    actor = _create_user()
    _create_user(
        email="corp@example.com",
        role="corp",
        corporation="diego_martin_regional_corporati",
    )
    client = _client(actor)

    created = client.post(
        "/users",
        json={"email": "Sam@Example.com", "first_name": "Sam", "last_name": "Lee"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "sam@example.com"
    assert body["role"] == "dmu"
    assert body["is_active"] is True
    assert "corporation" not in body

    listed = client.get("/users")
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()}
    assert emails == {"ada@example.com", "sam@example.com"}


def test_duplicate_email_is_409():
    actor = _create_user()
    response = _client(actor).post("/users", json={"email": "ada@example.com"})
    assert response.status_code == 409


def test_update_user_name_and_email():
    actor = _create_user()
    target = _create_user(email="sam@example.com", first_name="Sam")
    response = _client(actor).patch(
        f"/users/{target.user_id}",
        json={"first_name": "Samantha", "email": "samantha@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Samantha"
    assert response.json()["email"] == "samantha@example.com"


def test_cannot_update_corp_user():
    actor = _create_user()
    corp = _create_user(email="corp@example.com", role="corp")
    response = _client(actor).patch(
        f"/users/{corp.user_id}", json={"first_name": "Nope"}
    )
    assert response.status_code == 404


def test_cannot_deactivate_or_delete_self():
    actor = _create_user()
    client = _client(actor)

    deactivated = client.post(f"/users/{actor.user_id}/deactivate")
    assert deactivated.status_code == 409

    deleted = client.delete(f"/users/{actor.user_id}")
    assert deleted.status_code == 409


def test_deactivate_revokes_refresh_tokens_and_delete_removes_row():
    actor = _create_user()
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
    assert client.get("/users").json() == [
        {
            "user_id": str(actor.user_id),
            "email": actor.email,
            "first_name": actor.first_name,
            "last_name": actor.last_name,
            "role": "dmu",
            "is_active": True,
            "last_login": None,
        }
    ]
