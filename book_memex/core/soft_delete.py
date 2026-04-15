"""Soft-delete helpers for memex-family records.

Every table with an `archived_at TIMESTAMP NULL` column participates.
Convention: archived rows are filtered out of default queries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Type

from sqlalchemy.orm import Query, Session


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def filter_active(query: Query, model: Type, *, include_archived: bool = False) -> Query:
    """Filter a query to exclude archived rows unless `include_archived` is True."""
    if include_archived:
        return query
    return query.filter(model.archived_at.is_(None))


def archive(session: Session, instance) -> None:
    """Mark a single row as archived. Caller must commit."""
    instance.archived_at = _utc_now()
    session.add(instance)


def restore(session: Session, instance) -> None:
    """Clear archived_at on a row. Caller must commit."""
    instance.archived_at = None
    session.add(instance)


def hard_delete(session: Session, instance) -> None:
    """Delete a row physically. Caller must commit."""
    session.delete(instance)


def is_archived(instance) -> bool:
    """Whether a row is currently archived."""
    return getattr(instance, "archived_at", None) is not None
