"""SQLite engine factory with foreign-key enforcement."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "agentflow.db"


def sqlite_url(path: Path | None = None) -> str:
    """Build a SQLite URL. Does not create directories."""
    db_path = path or DEFAULT_SQLITE_PATH
    return f"sqlite:///{db_path.as_posix()}"


def _sqlite_file_path(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    remainder = url.removeprefix("sqlite:///")
    if remainder in {"", ":memory:"} or remainder.startswith(":memory:"):
        return None
    return Path(remainder)


def ensure_sqlite_parent_dir(url: str) -> None:
    """Create the parent directory for a file-backed SQLite URL when missing."""
    path = _sqlite_file_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_sqlite_engine(url: str | None = None) -> Engine:
    """Create an engine, ensure the DB directory exists, and enable SQLite FKs.

    Desktop packaging will later supply an OS-appropriate user-data path.
    The persistence layer only ensures the configured parent directory exists.
    """
    resolved = url or sqlite_url()
    ensure_sqlite_parent_dir(resolved)
    engine = create_engine(resolved, future=True)
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
