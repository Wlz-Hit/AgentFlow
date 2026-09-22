"""Append-only SQLAlchemy event repository."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.events import RuntimeEvent, StoredEvent, ensure_json_payload
from agentflow.persistence.models import RuntimeEventRow


def _row_to_stored(row: RuntimeEventRow) -> StoredEvent:
    payload = json.loads(row.payload_json)
    if not isinstance(payload, dict):
        raise DomainError("persisted event payload must be a JSON object")
    event = RuntimeEvent(
        id=row.event_id,
        event_type=row.event_type,
        occurred_at=row.occurred_at,
        payload=payload,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        job_id=row.job_id,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
    )
    return StoredEvent(position=row.position, event=event)


class SqlAlchemyEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: RuntimeEvent) -> StoredEvent:
        payload = ensure_json_payload(dict(event.payload))
        row = RuntimeEventRow(
            event_id=event.id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            job_id=event.job_id,
            occurred_at=event.occurred_at,
            payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            message = str(exc.orig) if getattr(exc, "orig", None) is not None else str(exc)
            if "event_id" in message.lower() or "unique" in message.lower():
                raise DomainError("event_id must be unique") from exc
            raise
        self._session.refresh(row)
        return _row_to_stored(row)

    def get(self, event_id: UUID) -> StoredEvent | None:
        row = self._session.scalar(
            select(RuntimeEventRow).where(RuntimeEventRow.event_id == event_id)
        )
        return _row_to_stored(row) if row is not None else None

    def list_after(self, position: int) -> list[StoredEvent]:
        rows = self._session.scalars(
            select(RuntimeEventRow)
            .where(RuntimeEventRow.position > position)
            .order_by(RuntimeEventRow.position)
        ).all()
        return [_row_to_stored(row) for row in rows]

    def list_for_job(self, job_id: UUID) -> list[StoredEvent]:
        rows = self._session.scalars(
            select(RuntimeEventRow)
            .where(RuntimeEventRow.job_id == job_id)
            .order_by(RuntimeEventRow.position)
        ).all()
        return [_row_to_stored(row) for row in rows]
