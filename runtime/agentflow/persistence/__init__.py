"""SQLite persistence (SQLAlchemy 2 + Alembic).

Domain entities map through repositories and mappers. Application code depends
on ``agentflow.core.ports`` protocols, not ORM rows.
"""

from agentflow.persistence.database import create_sqlite_engine, session_factory, sqlite_url
from agentflow.persistence.models import Base
from agentflow.persistence.unit_of_work import SqlAlchemyUnitOfWork, unit_of_work

__all__ = [
    "Base",
    "SqlAlchemyUnitOfWork",
    "create_sqlite_engine",
    "session_factory",
    "sqlite_url",
    "unit_of_work",
]
