"""
Personal metadata service for managing user-specific book data.

Handles ratings, favorites, reading status, progress tracking, and personal tags.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..db.models import Book, PersonalMetadata

logger = logging.getLogger(__name__)


class PersonalMetadataService:
    """Service for managing personal metadata for books."""

    def __init__(self, session: Session):
        """
        Initialize the personal metadata service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def get(self, book_id: int) -> Optional[PersonalMetadata]:
        """
        Get personal metadata for a book.

        Args:
            book_id: Book ID

        Returns:
            PersonalMetadata instance or None if not found
        """
        return self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

    def get_or_create(self, book_id: int) -> PersonalMetadata:
        """
        Get or create personal metadata for a book.

        Args:
            book_id: Book ID

        Returns:
            PersonalMetadata instance (created if didn't exist)
        """
        personal = self.get(book_id)
        if not personal:
            personal = PersonalMetadata(book_id=book_id)
            self.session.add(personal)
            self.session.flush()
        return personal

    def set_rating(self, book_id: int, rating: Optional[float]) -> PersonalMetadata:
        """
        Set rating for a book.

        Args:
            book_id: Book ID
            rating: Rating value (0-5, or None to clear)

        Returns:
            Updated PersonalMetadata instance
        """
        if rating is not None and (rating < 0 or rating > 5):
            raise ValueError("Rating must be between 0 and 5")

        personal = self.get_or_create(book_id)
        personal.rating = rating
        self.session.commit()
        logger.debug(f"Set rating for book {book_id}: {rating}")
        return personal

    def set_favorite(self, book_id: int, is_favorite: bool = True) -> PersonalMetadata:
        """
        Mark or unmark a book as favorite.

        Args:
            book_id: Book ID
            is_favorite: True to mark as favorite, False to unmark

        Returns:
            Updated PersonalMetadata instance
        """
        personal = self.get_or_create(book_id)
        personal.favorite = is_favorite
        self.session.commit()
        logger.debug(f"Set favorite for book {book_id}: {is_favorite}")
        return personal

    def set_reading_status(
        self,
        book_id: int,
        status: str,
        progress: Optional[int] = None,
    ) -> PersonalMetadata:
        """
        Set reading status for a book.

        Args:
            book_id: Book ID
            status: Reading status (unread, reading, read, abandoned)
            progress: Optional reading progress (0-100)

        Returns:
            Updated PersonalMetadata instance
        """
        valid_statuses = {'unread', 'reading', 'read', 'abandoned'}
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")

        if progress is not None and (progress < 0 or progress > 100):
            raise ValueError("Progress must be between 0 and 100")

        personal = self.get_or_create(book_id)
        personal.reading_status = status

        if progress is not None:
            personal.reading_progress = progress

        # Update dates based on status
        if status == 'reading' and not personal.date_started:
            personal.date_started = datetime.now()
        elif status == 'read':
            personal.date_finished = datetime.now()
            personal.reading_progress = 100

        self.session.commit()
        logger.debug(f"Set reading status for book {book_id}: {status}")
        return personal

    def update_progress(self, book_id: int, progress: int) -> PersonalMetadata:
        """
        Update reading progress for a book.

        Args:
            book_id: Book ID
            progress: Reading progress percentage (0-100)

        Returns:
            Updated PersonalMetadata instance
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        personal = self.get_or_create(book_id)
        personal.reading_progress = progress

        # Auto-update status based on progress
        if progress > 0 and personal.reading_status == 'unread':
            personal.reading_status = 'reading'
            if not personal.date_started:
                personal.date_started = datetime.now()
        elif progress == 100:
            personal.reading_status = 'read'
            personal.date_finished = datetime.now()

        self.session.commit()
        logger.debug(f"Updated progress for book {book_id}: {progress}%")
        return personal

    def set_owned(self, book_id: int, owned: bool = True) -> PersonalMetadata:
        """
        Set whether a book is owned.

        Args:
            book_id: Book ID
            owned: True if owned, False if borrowed/library

        Returns:
            Updated PersonalMetadata instance
        """
        personal = self.get_or_create(book_id)
        personal.owned = owned
        self.session.commit()
        logger.debug(f"Set owned for book {book_id}: {owned}")
        return personal

    def add_personal_tags(self, book_id: int, tags: List[str]) -> PersonalMetadata:
        """
        Add personal tags to a book.

        Args:
            book_id: Book ID
            tags: List of tag strings to add

        Returns:
            Updated PersonalMetadata instance
        """
        personal = self.get_or_create(book_id)
        existing_tags = personal.personal_tags or []

        # Add new tags (avoiding duplicates)
        for tag in tags:
            if tag and tag not in existing_tags:
                existing_tags.append(tag)

        personal.personal_tags = existing_tags
        self.session.commit()
        logger.debug(f"Added personal tags to book {book_id}: {tags}")
        return personal

    def remove_personal_tags(self, book_id: int, tags: List[str]) -> PersonalMetadata:
        """
        Remove personal tags from a book.

        Args:
            book_id: Book ID
            tags: List of tag strings to remove

        Returns:
            Updated PersonalMetadata instance
        """
        personal = self.get(book_id)
        if not personal or not personal.personal_tags:
            return personal

        personal.personal_tags = [t for t in personal.personal_tags if t not in tags]
        self.session.commit()
        logger.debug(f"Removed personal tags from book {book_id}: {tags}")
        return personal

    def get_favorites(self) -> List[Book]:
        """
        Get all favorite books.

        Returns:
            List of favorite books
        """
        return self.session.query(Book).join(Book.personal).filter(
            PersonalMetadata.favorite == True
        ).all()

    def get_by_status(self, status: str) -> List[Book]:
        """
        Get books by reading status.

        Args:
            status: Reading status to filter by

        Returns:
            List of books with the specified status
        """
        return self.session.query(Book).join(Book.personal).filter(
            PersonalMetadata.reading_status == status
        ).all()

    def get_by_rating(self, min_rating: float, max_rating: float = 5.0) -> List[Book]:
        """
        Get books within a rating range.

        Args:
            min_rating: Minimum rating (inclusive)
            max_rating: Maximum rating (inclusive)

        Returns:
            List of books within the rating range
        """
        return self.session.query(Book).join(Book.personal).filter(
            PersonalMetadata.rating >= min_rating,
            PersonalMetadata.rating <= max_rating
        ).order_by(PersonalMetadata.rating.desc()).all()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get personal metadata statistics.

        Returns:
            Dictionary with statistics about personal metadata
        """
        from sqlalchemy import func

        stats = {
            "total_with_metadata": self.session.query(PersonalMetadata).count(),
            "favorites_count": self.session.query(PersonalMetadata).filter(
                PersonalMetadata.favorite == True
            ).count(),
            "by_status": {},
            "by_rating": {},
            "in_queue": self.session.query(PersonalMetadata).filter(
                PersonalMetadata.queue_position.isnot(None)
            ).count(),
        }

        # Count by status
        status_counts = self.session.query(
            PersonalMetadata.reading_status,
            func.count(PersonalMetadata.id)
        ).group_by(PersonalMetadata.reading_status).all()

        for status, count in status_counts:
            if status:
                stats["by_status"][status] = count

        # Count by rating
        rating_counts = self.session.query(
            func.round(PersonalMetadata.rating),
            func.count(PersonalMetadata.id)
        ).filter(
            PersonalMetadata.rating.isnot(None)
        ).group_by(func.round(PersonalMetadata.rating)).all()

        for rating, count in rating_counts:
            if rating is not None:
                stats["by_rating"][int(rating)] = count

        # Average rating
        avg_rating = self.session.query(
            func.avg(PersonalMetadata.rating)
        ).filter(PersonalMetadata.rating.isnot(None)).scalar()
        stats["average_rating"] = round(avg_rating, 2) if avg_rating else None

        return stats

    def to_dict(self, book_id: int) -> Optional[Dict[str, Any]]:
        """
        Get personal metadata as a dictionary.

        Args:
            book_id: Book ID

        Returns:
            Dictionary representation or None if no metadata
        """
        personal = self.get(book_id)
        if not personal:
            return None

        return {
            "rating": personal.rating,
            "is_favorite": personal.favorite,
            "reading_status": personal.reading_status,
            "reading_progress": personal.reading_progress,
            "owned": personal.owned,
            "queue_position": personal.queue_position,
            "personal_tags": personal.personal_tags or [],
            "date_added": personal.date_added.isoformat() if personal.date_added else None,
            "date_started": personal.date_started.isoformat() if personal.date_started else None,
            "date_finished": personal.date_finished.isoformat() if personal.date_finished else None,
        }
