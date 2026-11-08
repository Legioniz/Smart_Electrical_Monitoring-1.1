from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .config import settings


def build_engine(url: str | None = None, *, testing: bool = False) -> Engine:
    target = url or settings.database_url
    if not target:
        raise RuntimeError("DATABASE_URL is not configured. See .env.example and README.md.")
    if target.startswith("sqlite"):
        if not testing:
            raise RuntimeError("SQLite is allowed only in the automated test profile; local app storage is MySQL.")
        return create_engine(target, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if not target.startswith("mysql+mysqlconnector://"):
        raise RuntimeError("Only the local MySQL Connector/Python URL is supported.")
    engine = create_engine(
        target,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=3,
        connect_args={"connection_timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def set_mysql_session_defaults(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
        finally:
            cursor.close()

    return engine


def build_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
