from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # A capture turn holds its connection for the whole model call, so the
    # default pool (5 + 10 overflow) can run dry when a corporation's worth of
    # officers send at once. 30 per process, two API processes, stays well
    # under Postgres's default max_connections of 100.
    return create_engine(url, pool_size=20, max_overflow=10)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
