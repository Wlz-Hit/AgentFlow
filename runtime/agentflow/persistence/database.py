"""SQLite engine factory. Domain schema is deferred."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "agentflow.db"


def sqlite_url(path: Path | None = None) -> str:
    db_path = path or DEFAULT_SQLITE_PATH
    return f"sqlite:///{db_path.as_posix()}"


def create_sqlite_engine(url: str | None = None) -> Engine:
    return create_engine(url or sqlite_url(), future=True)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def iter_sessions(engine: Engine) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
