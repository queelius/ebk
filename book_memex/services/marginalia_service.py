"""
Marginalia service for managing reader's notes, highlights, and observations.

Marginalia generalize annotations: they can be anchored to a location in a book,
apply to a whole book, span multiple books, or float free as collection-level notes.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..db.models import Book, Marginalia, marginalia_books
from ..core.soft_delete import (
    filter_active,
    archive as _archive,
    restore as _restore,
    hard_delete as _hard_delete,
)

logger = logging.getLogger(__name__)


class MarginaliaService:
    """Service for managing marginalia across books."""

    def __init__(self, session: Session, library_path=None):
        self.session = session
        self.library_path = library_path

    def create(
        self,
        content: Optional[str] = None,
        highlighted_text: Optional[str] = None,
        book_ids: Optional[List[int]] = None,
        page_number: Optional[int] = None,
        position: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        color: Optional[str] = None,
        pinned: bool = False,
    ) -> Marginalia:
        """Create a new marginalia entry.

        Args:
            content: The reader's note (markdown).
            highlighted_text: The passage being annotated.
            book_ids: Books this entry relates to (0, 1, or many).
            page_number: Page number (for location-scoped entries).
            position: Position info (char_offset, cfi, x/y coordinates).
            category: User-defined category.
            color: Hex color string (e.g. "#ff0000") for highlights.
            pinned: Pin to top.

        Returns:
            Created Marginalia instance.
        """
        if not content and not highlighted_text:
            raise ValueError("At least one of content or highlighted_text is required")

        entry = Marginalia(
            content=content,
            highlighted_text=highlighted_text,
            page_number=page_number,
            position=position,
            category=category,
            color=color,
            pinned=pinned,
        )
        self.session.add(entry)
        self.session.flush()  # Get the ID

        if book_ids:
            for book_id in book_ids:
                book = self.session.get(Book, book_id)
                if book:
                    entry.books.append(book)

        self.session.commit()
        return entry

    def get(self, marginalia_id: int) -> Optional[Marginalia]:
        """Get a marginalia entry by ID."""
        return self.session.get(Marginalia, marginalia_id)

    def get_by_uuid(self, uuid: str) -> Optional[Marginalia]:
        """Fetch a marginalia row by its uuid. Returns None if not found."""
        return (
            self.session.query(Marginalia)
            .filter_by(uuid=uuid)
            .first()
        )

    def list_for_book(
        self,
        book_id: int,
        category: Optional[str] = None,
        location_only: bool = False,
        scope: Optional[str] = None,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> List[Marginalia]:
        """List marginalia associated with a book.

        Args:
            book_id: Book ID.
            category: Optional filter by category.
            location_only: If True, only return location-scoped entries.
            scope: Optional filter ("highlight", "book_note", "collection_note",
                "cross_book_note"). Applied in Python after the DB filter
                because scope is a derived property.
            include_archived: If True, include archived entries. Default False.
            limit: Maximum number of rows to return.

        Returns:
            List of Marginalia entries, ordered by pinned, page then date.
        """
        query = (
            self.session.query(Marginalia)
            .join(marginalia_books)
            .filter(marginalia_books.c.book_id == book_id)
        )

        if category:
            query = query.filter(Marginalia.category == category)

        if location_only:
            query = query.filter(Marginalia.page_number.isnot(None))

        query = filter_active(query, Marginalia, include_archived=include_archived)

        query = query.order_by(
            Marginalia.pinned.desc(),
            Marginalia.page_number.asc().nulls_last(),
            Marginalia.created_at.desc(),
        )

        # If no post-query scope filter, we can limit at the SQL layer.
        # If scope is requested, we must fetch all and limit after filtering
        # (otherwise the limit cuts off rows before they've been scope-filtered).
        if limit is not None and not scope:
            query = query.limit(limit)

        rows = query.all()
        if scope:
            rows = [r for r in rows if r.scope == scope]
            if limit is not None:
                rows = rows[:limit]
        return rows

    def list_unattached(self, category: Optional[str] = None) -> List[Marginalia]:
        """List marginalia not attached to any book (collection-level)."""
        query = (
            self.session.query(Marginalia)
            .outerjoin(marginalia_books)
            .filter(marginalia_books.c.marginalia_id.is_(None))
        )

        if category:
            query = query.filter(Marginalia.category == category)

        return query.order_by(
            Marginalia.pinned.desc(),
            Marginalia.created_at.desc(),
        ).all()

    def update(
        self,
        marginalia_id: int,
        content: Optional[str] = ...,
        highlighted_text: Optional[str] = ...,
        page_number: Optional[int] = ...,
        category: Optional[str] = ...,
        pinned: Optional[bool] = None,
        book_ids: Optional[List[int]] = None,
    ) -> Optional[Marginalia]:
        """Update a marginalia entry. Pass ... (default) to leave unchanged."""
        entry = self.get(marginalia_id)
        if not entry:
            return None

        if content is not ...:
            entry.content = content
        if highlighted_text is not ...:
            entry.highlighted_text = highlighted_text
        if page_number is not ...:
            entry.page_number = page_number
        if category is not ...:
            entry.category = category
        if pinned is not None:
            entry.pinned = pinned
        if book_ids is not None:
            entry.books = [
                b for b in (self.session.get(Book, bid) for bid in book_ids) if b
            ]

        self.session.commit()
        return entry

    def delete(self, marginalia_id: int) -> bool:
        """Delete a marginalia entry."""
        entry = self.get(marginalia_id)
        if not entry:
            return False
        self.session.delete(entry)
        self.session.commit()
        return True

    def delete_all_for_book(self, book_id: int) -> int:
        """Delete all marginalia that are exclusively attached to this book."""
        entries = self.list_for_book(book_id)
        count = 0
        for entry in entries:
            if len(entry.books) == 1:
                self.session.delete(entry)
                count += 1
        self.session.commit()
        return count

    def archive(self, entry: Marginalia) -> None:
        """Soft-delete a marginalia entry (set archived_at)."""
        _archive(self.session, entry)
        self.session.commit()

    def restore(self, entry: Marginalia) -> None:
        """Clear the archived_at flag on a marginalia entry."""
        _restore(self.session, entry)
        self.session.commit()

    def hard_delete(self, entry: Marginalia) -> None:
        """Permanently delete a marginalia entry from the database."""
        _hard_delete(self.session, entry)
        self.session.commit()

    def count(self, book_id: Optional[int] = None) -> int:
        """Count marginalia entries, optionally filtered by book."""
        query = self.session.query(Marginalia)
        if book_id is not None:
            query = query.join(marginalia_books).filter(
                marginalia_books.c.book_id == book_id
            )
        return query.count()

    def export(self, book_id: int, format_type: str = 'json') -> str:
        """Export marginalia for a book."""
        entries = self.list_for_book(book_id)
        book = self.session.get(Book, book_id)

        if format_type == 'markdown':
            return self._export_markdown(book, entries)
        return self._export_json(book, entries)

    def _export_json(self, book: Optional[Book], entries: List[Marginalia]) -> str:
        data = {
            "book_id": book.id if book else None,
            "book_title": book.title if book else "Unknown",
            "marginalia": [
                {
                    "id": m.id,
                    "content": m.content,
                    "highlighted_text": m.highlighted_text,
                    "page": m.page_number,
                    "category": m.category,
                    "pinned": m.pinned,
                    "books": [b.id for b in m.books],
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in entries
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_markdown(self, book: Optional[Book], entries: List[Marginalia]) -> str:
        title = book.title if book else "Unknown Book"
        lines = [f"# Marginalia: {title}\n"]

        for m in entries:
            page_info = f" (p. {m.page_number})" if m.page_number else ""
            if m.highlighted_text:
                lines.append(f"> {m.highlighted_text}{page_info}")
                if m.content:
                    lines.append(f"\n{m.content}\n")
                else:
                    lines.append("")
            elif m.content:
                lines.append(f"- {m.content}{page_info}\n")

        return "\n".join(lines)

    def to_dict(self, entry: Marginalia) -> Dict[str, Any]:
        """Convert a marginalia entry to a dictionary."""
        return {
            "id": entry.id,
            "content": entry.content,
            "highlighted_text": entry.highlighted_text,
            "page": entry.page_number,
            "position": entry.position,
            "category": entry.category,
            "pinned": entry.pinned,
            "book_ids": [b.id for b in entry.books],
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
