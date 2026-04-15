"""
Reading queue service for managing the reading queue.

Provides operations for adding, removing, reordering, and querying
books in the reading queue.
"""

from typing import List, Optional
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.models import Book, PersonalMetadata

logger = logging.getLogger(__name__)


class ReadingQueueService:
    """Service for managing the reading queue."""

    def __init__(self, session: Session):
        """
        Initialize the reading queue service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def get_queue(self) -> List[Book]:
        """
        Get all books in the reading queue, ordered by position.

        Returns:
            List of books in queue order
        """
        return self.session.query(Book).join(Book.personal).filter(
            PersonalMetadata.queue_position.isnot(None)
        ).order_by(PersonalMetadata.queue_position).all()

    def get_next(self) -> Optional[Book]:
        """
        Get the next book in the reading queue (position 1).

        Returns:
            The book at the top of the queue, or None if queue is empty
        """
        return self.session.query(Book).join(Book.personal).filter(
            PersonalMetadata.queue_position == 1
        ).first()

    def get_position(self, book_id: int) -> Optional[int]:
        """
        Get the position of a book in the queue.

        Args:
            book_id: Book ID to check

        Returns:
            Queue position (1-based) or None if not in queue
        """
        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if personal:
            return personal.queue_position
        return None

    def is_in_queue(self, book_id: int) -> bool:
        """
        Check if a book is in the queue.

        Args:
            book_id: Book ID to check

        Returns:
            True if book is in queue
        """
        return self.get_position(book_id) is not None

    def add(self, book_id: int, position: Optional[int] = None) -> int:
        """
        Add a book to the reading queue.

        Args:
            book_id: Book ID to add
            position: Position in queue (1-based). If None, adds to end.

        Returns:
            The position where the book was added
        """
        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal:
            personal = PersonalMetadata(book_id=book_id)
            self.session.add(personal)
            self.session.flush()

        # If already in queue, just reorder
        if personal.queue_position is not None:
            if position is not None:
                self.reorder(book_id, position)
            return personal.queue_position

        # Get current max position
        max_pos = self.session.query(
            func.max(PersonalMetadata.queue_position)
        ).scalar() or 0

        if position is None:
            # Add to end
            personal.queue_position = max_pos + 1
        else:
            # Insert at specific position, shift others down
            position = max(1, position)
            self.session.query(PersonalMetadata).filter(
                PersonalMetadata.queue_position >= position,
                PersonalMetadata.queue_position.isnot(None)
            ).update({
                PersonalMetadata.queue_position: PersonalMetadata.queue_position + 1
            })
            personal.queue_position = position

        self.session.commit()
        logger.info(f"Added book {book_id} to queue at position {personal.queue_position}")
        return personal.queue_position

    def remove(self, book_id: int) -> bool:
        """
        Remove a book from the reading queue.

        Args:
            book_id: Book ID to remove

        Returns:
            True if book was removed, False if it wasn't in queue
        """
        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal or personal.queue_position is None:
            return False

        old_position = personal.queue_position
        personal.queue_position = None

        # Shift other items up to fill gap
        self.session.query(PersonalMetadata).filter(
            PersonalMetadata.queue_position > old_position
        ).update({
            PersonalMetadata.queue_position: PersonalMetadata.queue_position - 1
        })

        self.session.commit()
        logger.info(f"Removed book {book_id} from queue")
        return True

    def reorder(self, book_id: int, new_position: int) -> bool:
        """
        Move a book to a new position in the queue.

        Args:
            book_id: Book ID to move
            new_position: New position (1-based)

        Returns:
            True if book was reordered, False if it wasn't in queue
        """
        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal or personal.queue_position is None:
            # Not in queue, add it
            self.add(book_id, new_position)
            return True

        old_position = personal.queue_position
        new_position = max(1, new_position)

        if old_position == new_position:
            return True

        if old_position < new_position:
            # Moving down: shift items between old and new up
            self.session.query(PersonalMetadata).filter(
                PersonalMetadata.queue_position > old_position,
                PersonalMetadata.queue_position <= new_position,
                PersonalMetadata.queue_position.isnot(None)
            ).update({
                PersonalMetadata.queue_position: PersonalMetadata.queue_position - 1
            })
        else:
            # Moving up: shift items between new and old down
            self.session.query(PersonalMetadata).filter(
                PersonalMetadata.queue_position >= new_position,
                PersonalMetadata.queue_position < old_position,
                PersonalMetadata.queue_position.isnot(None)
            ).update({
                PersonalMetadata.queue_position: PersonalMetadata.queue_position + 1
            })

        personal.queue_position = new_position
        self.session.commit()
        logger.info(f"Moved book {book_id} from position {old_position} to {new_position}")
        return True

    def clear(self) -> int:
        """
        Clear all books from the reading queue.

        Returns:
            Number of books removed from queue
        """
        count = self.session.query(PersonalMetadata).filter(
            PersonalMetadata.queue_position.isnot(None)
        ).count()

        self.session.query(PersonalMetadata).filter(
            PersonalMetadata.queue_position.isnot(None)
        ).update({PersonalMetadata.queue_position: None})

        self.session.commit()
        logger.info(f"Cleared reading queue ({count} items)")
        return count

    def count(self) -> int:
        """
        Get the number of books in the queue.

        Returns:
            Number of books in queue
        """
        return self.session.query(PersonalMetadata).filter(
            PersonalMetadata.queue_position.isnot(None)
        ).count()

    def pop_next(self) -> Optional[Book]:
        """
        Remove and return the next book from the queue.

        Returns:
            The book that was at position 1, or None if queue is empty
        """
        book = self.get_next()
        if book:
            self.remove(book.id)
        return book
