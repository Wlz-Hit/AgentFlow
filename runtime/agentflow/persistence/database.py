"""SQLite engine factory with foreign-key enforcement."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "agentflow.db"


def sqlite_url(path: Path | None = None) -> str:
    db_path = path or DEFAULT_SQLITE_PATH
    return f"sqlite:///{db_path.as_posix()}"


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_sqlite_engine(url: str | None = None) -> Engine:
    """Create an engine and enable SQLite foreign-key checks on every connection."""
    engine = create_engine(url or sqlite_url(), future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def iter_sessions(engine: Engine) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
