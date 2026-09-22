"""Shared migration helpers for persistence tests."""

from __future__ import annotations

from pathlib import Path

from agentflow.persistence.database import create_sqlite_engine, session_factory
from agentflow.persistence.unit_of_work import SqlAlchemyUnitOfWork
from alembic import command
from alembic.config import Config

RUNTIME_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "0003_event_log"


def alembic_config(db_path: Path) -> Config:
    cfg = Config(str(RUNTIME_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(RUNTIME_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def migrate_to(db_path: Path, revision: str = "head") -> None:
    command.upgrade(alembic_config(db_path), revision)


def migrate_down(db_path: Path, revision: str = "base") -> None:
    command.downgrade(alembic_config(db_path), revision)


def reopen(db_url: str) -> SqlAlchemyUnitOfWork:
    engine = create_sqlite_engine(db_url)
    return SqlAlchemyUnitOfWork(session_factory(engine))
