"""
Database-backed Library class for ebk.

Provides a fluent API for managing ebook libraries using SQLAlchemy + SQLite.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from .db.models import Book, Author, Subject, File, ExtractedText, PersonalMetadata
from .db.session import init_db, get_session, close_db
from .services.import_service import ImportService
from .services.text_extraction import TextExtractionService

logger = logging.getLogger(__name__)


class Library:
    """
    Database-backed library for managing ebooks.

    Usage:
        lib = Library.open("/path/to/library")
        lib.add_book(Path("book.pdf"), {"title": "My Book", "creators": ["Author"]})
        results = lib.search("python programming")
        stats = lib.stats()
        lib.close()
    """

    def __init__(self, library_path: Path, session: Session):
        self.library_path = Path(library_path)
        self.session = session
        self.import_service = ImportService(library_path, session)
        self.text_service = TextExtractionService(library_path)

    @classmethod
    def open(cls, library_path: Path, echo: bool = False) -> 'Library':
        """
        Open or create a library.

        Args:
            library_path: Path to library directory
            echo: If True, log all SQL statements

        Returns:
            Library instance
        """
        library_path = Path(library_path)
        init_db(library_path, echo=echo)
        session = get_session()

        logger.info(f"Opened library at {library_path}")
        return cls(library_path, session)

    def close(self):
        """Close library and cleanup database connection."""
        if self.session:
            self.session.close()
        close_db()
        logger.info("Closed library")

    def add_book(self, file_path: Path, metadata: Dict[str, Any],
                 extract_text: bool = True, extract_cover: bool = True) -> Optional[Book]:
        """
        Add a book to the library.

        Args:
            file_path: Path to ebook file
            metadata: Metadata dictionary (title, creators, subjects, etc.)
            extract_text: Whether to extract full text
            extract_cover: Whether to extract cover image

        Returns:
            Book instance or None if import failed
        """
        book = self.import_service.import_file(
            file_path,
            metadata,
            extract_text=extract_text,
            extract_cover=extract_cover
        )

        if book:
            logger.info(f"Added book: {book.title}")

        return book

    def add_calibre_book(self, metadata_opf_path: Path) -> Optional[Book]:
        """
        Add book from Calibre metadata.opf file.

        Args:
            metadata_opf_path: Path to metadata.opf

        Returns:
            Book instance or None
        """
        return self.import_service.import_calibre_book(metadata_opf_path)

    def batch_import(self, files_and_metadata: List[Tuple[Path, Dict[str, Any]]],
                    show_progress: bool = True) -> List[Book]:
        """
        Import multiple books with progress tracking.

        Args:
            files_and_metadata: List of (file_path, metadata) tuples
            show_progress: Whether to show progress bar

        Returns:
            List of imported Book instances
        """
        file_paths = [f for f, _ in files_and_metadata]
        metadata_list = [m for _, m in files_and_metadata]

        return self.import_service.batch_import(
            file_paths,
            metadata_list,
            show_progress=show_progress
        )

    def get_book(self, book_id: int) -> Optional[Book]:
        """Get book by ID."""
        return self.session.query(Book).get(book_id)

    def get_book_by_unique_id(self, unique_id: str) -> Optional[Book]:
        """Get book by unique ID."""
        return self.session.query(Book).filter_by(unique_id=unique_id).first()

    def query(self) -> 'QueryBuilder':
        """Start a fluent query."""
        return QueryBuilder(self.session)

    def search(self, query: str, limit: int = 50) -> List[Book]:
        """
        Full-text search across books.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching books
        """
        try:
            result = self.session.execute(
                """
                SELECT book_id, rank
                FROM books_fts
                WHERE books_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            )

            book_ids = [row[0] for row in result]

            if not book_ids:
                return []

            # Fetch books maintaining search order
            books = self.session.query(Book).filter(Book.id.in_(book_ids)).all()
            books_dict = {b.id: b for b in books}
            return [books_dict[bid] for bid in book_ids if bid in books_dict]

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def stats(self) -> Dict[str, Any]:
        """
        Get library statistics.

        Returns:
            Dictionary with statistics
        """
        total_books = self.session.query(func.count(Book.id)).scalar()
        total_authors = self.session.query(func.count(Author.id)).scalar()
        total_subjects = self.session.query(func.count(Subject.id)).scalar()
        total_files = self.session.query(func.count(File.id)).scalar()

        # Reading stats
        read_count = self.session.query(func.count(PersonalMetadata.id)).filter(
            PersonalMetadata.reading_status == 'read'
        ).scalar()

        reading_count = self.session.query(func.count(PersonalMetadata.id)).filter(
            PersonalMetadata.reading_status == 'reading'
        ).scalar()

        # Language distribution
        lang_dist = self.session.query(
            Book.language,
            func.count(Book.id)
        ).group_by(Book.language).all()

        # Format distribution
        format_dist = self.session.query(
            File.format,
            func.count(File.id)
        ).group_by(File.format).all()

        return {
            'total_books': total_books,
            'total_authors': total_authors,
            'total_subjects': total_subjects,
            'total_files': total_files,
            'read_count': read_count,
            'reading_count': reading_count,
            'languages': dict(lang_dist),
            'formats': dict(format_dist)
        }

    def get_all_books(self, limit: Optional[int] = None, offset: int = 0) -> List[Book]:
        """
        Get all books with optional pagination.

        Args:
            limit: Maximum number of books
            offset: Starting offset

        Returns:
            List of books
        """
        query = self.session.query(Book).order_by(Book.title)

        if limit:
            query = query.limit(limit).offset(offset)

        return query.all()

    def get_books_by_author(self, author_name: str) -> List[Book]:
        """Get all books by an author."""
        return self.session.query(Book).join(Book.authors).filter(
            Author.name.ilike(f"%{author_name}%")
        ).all()

    def get_books_by_subject(self, subject_name: str) -> List[Book]:
        """Get all books with a subject."""
        return self.session.query(Book).join(Book.subjects).filter(
            Subject.name.ilike(f"%{subject_name}%")
        ).all()

    def update_reading_status(self, book_id: int, status: str,
                             progress: Optional[int] = None,
                             rating: Optional[int] = None):
        """
        Update reading status for a book.

        Args:
            book_id: Book ID
            status: Reading status (unread, reading, read)
            progress: Reading progress percentage (0-100)
            rating: Rating (1-5)
        """
        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if personal:
            personal.reading_status = status
            if progress is not None:
                personal.reading_progress = progress
            if rating is not None:
                personal.rating = rating

            if status == 'read':
                personal.date_read = datetime.now()

            self.session.commit()
            logger.info(f"Updated reading status for book {book_id}: {status}")

    def delete_book(self, book_id: int, delete_files: bool = False):
        """
        Delete a book from the library.

        Args:
            book_id: Book ID
            delete_files: If True, also delete physical files
        """
        book = self.get_book(book_id)
        if not book:
            logger.warning(f"Book {book_id} not found")
            return

        # Delete physical files if requested
        if delete_files:
            for file in book.files:
                file_path = self.library_path / file.path
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted file: {file_path}")

            # Delete covers
            for cover in book.covers:
                cover_path = self.library_path / cover.path
                if cover_path.exists():
                    cover_path.unlink()

        # Delete from database (cascade will handle related records)
        self.session.delete(book)
        self.session.commit()
        logger.info(f"Deleted book: {book.title}")


class QueryBuilder:
    """Fluent query builder for books."""

    def __init__(self, session: Session):
        self.session = session
        self._query = session.query(Book)

    def filter_by_title(self, title: str, exact: bool = False) -> 'QueryBuilder':
        """Filter by title."""
        if exact:
            self._query = self._query.filter(Book.title == title)
        else:
            self._query = self._query.filter(Book.title.ilike(f"%{title}%"))
        return self

    def filter_by_author(self, author: str) -> 'QueryBuilder':
        """Filter by author name."""
        self._query = self._query.join(Book.authors).filter(
            Author.name.ilike(f"%{author}%")
        )
        return self

    def filter_by_subject(self, subject: str) -> 'QueryBuilder':
        """Filter by subject."""
        self._query = self._query.join(Book.subjects).filter(
            Subject.name.ilike(f"%{subject}%")
        )
        return self

    def filter_by_language(self, language: str) -> 'QueryBuilder':
        """Filter by language code."""
        self._query = self._query.filter(Book.language == language)
        return self

    def filter_by_publisher(self, publisher: str) -> 'QueryBuilder':
        """Filter by publisher."""
        self._query = self._query.filter(Book.publisher.ilike(f"%{publisher}%"))
        return self

    def filter_by_reading_status(self, status: str) -> 'QueryBuilder':
        """Filter by reading status."""
        self._query = self._query.join(Book.personal_metadata).filter(
            PersonalMetadata.reading_status == status
        )
        return self

    def filter_by_rating(self, min_rating: int, max_rating: int = 5) -> 'QueryBuilder':
        """Filter by rating range."""
        self._query = self._query.join(Book.personal_metadata).filter(
            and_(
                PersonalMetadata.rating >= min_rating,
                PersonalMetadata.rating <= max_rating
            )
        )
        return self

    def order_by(self, field: str, desc: bool = False) -> 'QueryBuilder':
        """
        Order results.

        Args:
            field: Field name (title, date_added, publication_date, rating)
            desc: Descending order if True
        """
        field_map = {
            'title': Book.title,
            'date_added': Book.date_added,
            'publication_date': Book.publication_date,
        }

        if field in field_map:
            order_field = field_map[field]
            if desc:
                order_field = order_field.desc()
            self._query = self._query.order_by(order_field)

        return self

    def limit(self, limit: int) -> 'QueryBuilder':
        """Limit number of results."""
        self._query = self._query.limit(limit)
        return self

    def offset(self, offset: int) -> 'QueryBuilder':
        """Set result offset."""
        self._query = self._query.offset(offset)
        return self

    def all(self) -> List[Book]:
        """Execute query and return all results."""
        return self._query.all()

    def first(self) -> Optional[Book]:
        """Execute query and return first result."""
        return self._query.first()

    def count(self) -> int:
        """Get count of matching books."""
        return self._query.count()
