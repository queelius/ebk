"""Service layer for ReadingSession records."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from book_memex.db.models import ReadingSession, Book
from book_memex.core.soft_delete import (
    filter_active, archive as _archive,
    restore as _restore, hard_delete as _hard_delete,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReadingSessionService:
    def __init__(self, session: Session, library_path=None):
        self.session = session
        self.library_path = library_path

    def start(
        self,
        book_id: int,
        start_anchor: Optional[Dict[str, Any]] = None,
    ) -> ReadingSession:
        book = self.session.get(Book, book_id)
        if book is None:
            raise LookupError(f"Book {book_id} not found")
        rs = ReadingSession(
            book_id=book_id,
            start_time=_utc_now(),
            start_anchor=start_anchor,
        )
        self.session.add(rs)
        self.session.commit()
        return rs

    def end(
        self,
        uuid: str,
        end_anchor: Optional[Dict[str, Any]] = None,
    ) -> ReadingSession:
        rs = self.get_by_uuid(uuid)
        if rs is None:
            raise LookupError(f"ReadingSession {uuid} not found")
        if rs.end_time is None:
            rs.end_time = _utc_now()
        if end_anchor is not None:
            rs.end_anchor = end_anchor
        self.session.commit()
        return rs

    def get_by_uuid(self, uuid: str) -> Optional[ReadingSession]:
        return (
            self.session.query(ReadingSession)
            .filter_by(uuid=uuid)
            .first()
        )

    def list_for_book(
        self,
        book_id: int,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> List[ReadingSession]:
        q = self.session.query(ReadingSession).filter_by(book_id=book_id)
        q = filter_active(q, ReadingSession, include_archived=include_archived)
        q = q.order_by(ReadingSession.start_time.desc())
        if limit:
            q = q.limit(limit)
        return q.all()

    def archive(self, rs: ReadingSession) -> None:
        _archive(self.session, rs)
        self.session.commit()

    def restore(self, rs: ReadingSession) -> None:
        _restore(self.session, rs)
        self.session.commit()

    def hard_delete(self, rs: ReadingSession) -> None:
        _hard_delete(self.session, rs)
        self.session.commit()
