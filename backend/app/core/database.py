
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine():
    settings = get_settings()

    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        connect_args={"connect_timeout": 10},
    )


engine = create_database_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
