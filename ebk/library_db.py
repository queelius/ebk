"""
Database-backed Library class for ebk.

Provides a fluent API for managing ebook libraries using SQLAlchemy + SQLite.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from sqlalchemy import func, or_, and_, text
from sqlalchemy.orm import Session

from .db.models import Book, Author, Subject, File, ExtractedText, PersonalMetadata
from .db.session import init_db, get_session, close_db
from .services.import_service import ImportService
from .services.text_extraction import TextExtractionService
from .search_parser import parse_search_query

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
        Advanced search across books with field-specific queries and boolean logic.

        Supports:
            - Field searches: title:Python, author:Knuth, tag:programming
            - Phrases: "machine learning"
            - Boolean: AND (implicit), OR (explicit), NOT/-prefix (negation)
            - Comparisons: rating:>=4, rating:3-5
            - Filters: language:en, format:pdf, favorite:true

        Examples:
            title:Python rating:>=4 format:pdf
            author:"Donald Knuth" series:TAOCP
            tag:programming favorite:true NOT java

        Args:
            query: Search query (supports advanced syntax or plain text)
            limit: Maximum number of results

        Returns:
            List of matching books
        """
        try:
            # Parse the query
            parsed = parse_search_query(query)

            # If no FTS terms and no filters, return empty
            if not parsed.has_fts_terms() and not parsed.has_filters():
                return []

            # Build the query
            book_ids = []

            # If we have FTS terms, search FTS5 first
            if parsed.has_fts_terms():
                result = self.session.execute(
                    text("""
                    SELECT book_id, rank
                    FROM books_fts
                    WHERE books_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                    """),
                    {"query": parsed.fts_query, "limit": limit * 2}  # Get more for filtering
                )
                book_ids = [row[0] for row in result]

                if not book_ids:
                    return []

            # Build filter conditions
            from .search_parser import SearchQueryParser
            parser = SearchQueryParser()
            where_clause, params = parser.to_sql_conditions(parsed)

            # If we have both FTS and filters, combine them
            if book_ids and where_clause:
                # Start with FTS results and apply filters
                books_query = self.session.query(Book).filter(
                    Book.id.in_(book_ids)
                )

                # Apply additional SQL filters
                if where_clause:
                    books_query = books_query.filter(text(where_clause).bindparams(**params))

                books = books_query.limit(limit).all()

                # Maintain FTS ranking order
                books_dict = {b.id: b for b in books}
                return [books_dict[bid] for bid in book_ids if bid in books_dict][:limit]

            # If only FTS (no additional filters)
            elif book_ids:
                books = self.session.query(Book).filter(Book.id.in_(book_ids)).all()
                books_dict = {b.id: b for b in books}
                return [books_dict[bid] for bid in book_ids if bid in books_dict][:limit]

            # If only filters (no FTS)
            elif where_clause:
                books_query = self.session.query(Book)
                books_query = books_query.filter(text(where_clause).bindparams(**params))
                return books_query.limit(limit).all()

            return []

        except Exception as e:
            logger.error(f"Search error: {e}")
            logger.exception(e)
            # Fallback to original simple FTS search
            try:
                result = self.session.execute(
                    text("""
                    SELECT book_id, rank
                    FROM books_fts
                    WHERE books_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                    """),
                    {"query": query, "limit": limit}
                )
                book_ids = [row[0] for row in result]
                if not book_ids:
                    return []
                books = self.session.query(Book).filter(Book.id.in_(book_ids)).all()
                books_dict = {b.id: b for b in books}
                return [books_dict[bid] for bid in book_ids if bid in books_dict]
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
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
                personal.date_finished = datetime.now()

            self.session.commit()
            logger.info(f"Updated reading status for book {book_id}: {status}")

    def set_favorite(self, book_id: int, favorite: bool = True):
        """
        Mark/unmark book as favorite.

        Args:
            book_id: Book ID
            favorite: True to mark as favorite, False to unmark
        """
        from .db.models import PersonalMetadata

        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal:
            # Create personal metadata if it doesn't exist
            personal = PersonalMetadata(book_id=book_id, favorite=favorite)
            self.session.add(personal)
        else:
            personal.favorite = favorite

        self.session.commit()
        logger.info(f"Set favorite for book {book_id}: {favorite}")

    def add_tags(self, book_id: int, tags: List[str]):
        """
        Add personal tags to a book.

        Args:
            book_id: Book ID
            tags: List of tag strings
        """
        from .db.models import PersonalMetadata

        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal:
            personal = PersonalMetadata(book_id=book_id, personal_tags=tags)
            self.session.add(personal)
        else:
            existing_tags = personal.personal_tags or []
            # Add new tags without duplicates
            combined = list(set(existing_tags + tags))
            personal.personal_tags = combined

        self.session.commit()
        logger.info(f"Added tags to book {book_id}: {tags}")

    def remove_tags(self, book_id: int, tags: List[str]):
        """
        Remove personal tags from a book.

        Args:
            book_id: Book ID
            tags: List of tag strings to remove
        """
        from .db.models import PersonalMetadata

        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if personal and personal.personal_tags:
            personal.personal_tags = [t for t in personal.personal_tags if t not in tags]
            self.session.commit()
            logger.info(f"Removed tags from book {book_id}: {tags}")

    def add_subject(self, book_id: int, subject_name: str):
        """
        Add a subject/tag to a book.

        Args:
            book_id: Book ID
            subject_name: Subject/tag name to add
        """
        book = self.session.query(Book).filter_by(id=book_id).first()
        if not book:
            logger.warning(f"Book {book_id} not found")
            return

        # Check if subject already exists
        subject = self.session.query(Subject).filter_by(name=subject_name).first()
        if not subject:
            subject = Subject(name=subject_name)
            self.session.add(subject)

        # Add subject to book if not already present
        if subject not in book.subjects:
            book.subjects.append(subject)
            self.session.commit()
            logger.info(f"Added subject '{subject_name}' to book {book_id}")

    def add_annotation(self, book_id: int, content: str,
                      page: Optional[int] = None,
                      annotation_type: str = 'note'):
        """
        Add an annotation/comment to a book.

        Args:
            book_id: Book ID
            content: Annotation text
            page: Page number (optional)
            annotation_type: Type of annotation (note, highlight, bookmark)

        Returns:
            Annotation ID
        """
        from .db.models import Annotation

        annotation = Annotation(
            book_id=book_id,
            content=content,
            page_number=page,
            annotation_type=annotation_type,
            created_at=datetime.now()
        )
        self.session.add(annotation)
        self.session.commit()

        logger.info(f"Added annotation to book {book_id}")
        return annotation.id

    def get_annotations(self, book_id: int) -> List:
        """
        Get all annotations for a book.

        Args:
            book_id: Book ID

        Returns:
            List of Annotation objects
        """
        from .db.models import Annotation

        return self.session.query(Annotation).filter_by(
            book_id=book_id
        ).order_by(Annotation.created_at.desc()).all()

    def delete_annotation(self, annotation_id: int):
        """
        Delete an annotation.

        Args:
            annotation_id: Annotation ID
        """
        from .db.models import Annotation

        annotation = self.session.query(Annotation).get(annotation_id)
        if annotation:
            self.session.delete(annotation)
            self.session.commit()
            logger.info(f"Deleted annotation {annotation_id}")

    def add_to_virtual_library(self, book_id: int, library_name: str):
        """
        Add a book to a virtual library (collection/view).

        Args:
            book_id: Book ID
            library_name: Name of the virtual library
        """
        from .db.models import PersonalMetadata

        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if not personal:
            # Use personal_tags as virtual_libraries array
            personal = PersonalMetadata(book_id=book_id, personal_tags=[library_name])
            self.session.add(personal)
        else:
            existing_libs = personal.personal_tags or []
            if library_name not in existing_libs:
                existing_libs.append(library_name)
                personal.personal_tags = existing_libs

        self.session.commit()
        logger.info(f"Added book {book_id} to virtual library '{library_name}'")

    def remove_from_virtual_library(self, book_id: int, library_name: str):
        """
        Remove a book from a virtual library.

        Args:
            book_id: Book ID
            library_name: Name of the virtual library
        """
        from .db.models import PersonalMetadata

        personal = self.session.query(PersonalMetadata).filter_by(
            book_id=book_id
        ).first()

        if personal and personal.personal_tags:
            personal.personal_tags = [lib for lib in personal.personal_tags if lib != library_name]
            self.session.commit()
            logger.info(f"Removed book {book_id} from virtual library '{library_name}'")

    def get_virtual_library(self, library_name: str) -> List[Book]:
        """
        Get all books in a virtual library.

        Args:
            library_name: Name of the virtual library

        Returns:
            List of books in this virtual library
        """
        from .db.models import PersonalMetadata
        from sqlalchemy import func

        # Query books where personal_tags contains the library_name
        # This works with SQLite's JSON support
        books = (self.session.query(Book)
                .join(Book.personal)
                .filter(PersonalMetadata.personal_tags.contains(library_name))
                .all())

        return books

    def list_virtual_libraries(self) -> List[str]:
        """
        Get all unique virtual library names.

        Returns:
            List of virtual library names
        """
        from .db.models import PersonalMetadata

        # Get all personal_tags arrays and flatten them
        all_metadata = self.session.query(PersonalMetadata).filter(
            PersonalMetadata.personal_tags.isnot(None)
        ).all()

        libraries = set()
        for pm in all_metadata:
            if pm.personal_tags:
                libraries.update(pm.personal_tags)

        return sorted(list(libraries))

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

    def find_similar(
        self,
        book_id: int,
        top_k: int = 10,
        similarity_config: Optional[Any] = None,
        filter_language: bool = True,
    ) -> List[Tuple[Book, float]]:
        """
        Find books similar to the given book.

        Uses semantic similarity based on content, metadata, etc.

        Args:
            book_id: ID of the query book
            top_k: Number of similar books to return (default 10)
            similarity_config: Optional BookSimilarity instance
                             (default: balanced preset)
            filter_language: If True, only return books in same language

        Returns:
            List of (book, similarity_score) tuples, sorted by similarity

        Example:
            >>> similar = lib.find_similar(42, top_k=5)
            >>> for book, score in similar:
            ...     print(f"{book.title}: {score:.2f}")
        """
        from ebk.similarity import BookSimilarity

        # Get query book
        query_book = self.get_book(book_id)
        if not query_book:
            logger.warning(f"Book {book_id} not found")
            return []

        # Get candidate books
        candidates_query = self.query()
        if filter_language and query_book.language:
            candidates_query = candidates_query.filter_by_language(query_book.language)

        candidates = candidates_query.all()

        if not candidates:
            return []

        # Configure similarity
        if similarity_config is None:
            similarity_config = BookSimilarity().balanced()

        # Fit on all candidates for performance
        similarity_config.fit(candidates)

        # Find similar books
        results = similarity_config.find_similar(query_book, candidates, top_k=top_k)

        logger.info(
            f"Found {len(results)} similar books to '{query_book.title}'"
        )

        return results

    def compute_similarity_matrix(
        self,
        book_ids: Optional[List[int]] = None,
        similarity_config: Optional[Any] = None,
    ) -> Tuple[List[Book], Any]:
        """
        Compute pairwise similarity matrix for books.

        Args:
            book_ids: Optional list of book IDs (default: all books)
            similarity_config: Optional BookSimilarity instance
                             (default: balanced preset)

        Returns:
            Tuple of (books, similarity_matrix)
            where similarity_matrix[i][j] = similarity(books[i], books[j])

        Example:
            >>> books, matrix = lib.compute_similarity_matrix()
            >>> # matrix[0][1] is similarity between books[0] and books[1]
        """
        from ebk.similarity import BookSimilarity

        # Get books
        if book_ids:
            books = [self.get_book(book_id) for book_id in book_ids]
            books = [b for b in books if b is not None]  # Filter None
        else:
            books = self.query().all()

        if not books:
            logger.warning("No books found for similarity matrix")
            return [], None

        # Configure similarity
        if similarity_config is None:
            similarity_config = BookSimilarity().balanced()

        # Fit and compute matrix
        similarity_config.fit(books)
        matrix = similarity_config.similarity_matrix(books)

        logger.info(f"Computed {len(books)}x{len(books)} similarity matrix")

        return books, matrix


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

    def filter_by_year(self, year: int) -> 'QueryBuilder':
        """Filter by publication year.

        Args:
            year: Publication year (e.g., 1975)

        Returns:
            Self for chaining
        """
        # publication_date can be "YYYY", "YYYY-MM", or "YYYY-MM-DD"
        # So we match if it starts with the year
        year_str = str(year)
        self._query = self._query.filter(Book.publication_date.like(f"{year_str}%"))
        return self

    def filter_by_text(self, search_text: str) -> 'QueryBuilder':
        """Filter by full-text search.

        Uses FTS5 to search across title, description, and extracted text.

        Args:
            search_text: Text to search for

        Returns:
            Self for chaining
        """
        from sqlalchemy import text as sql_text

        # Query FTS5 table for matching book IDs
        result = self.session.execute(
            sql_text("""
            SELECT book_id
            FROM books_fts
            WHERE books_fts MATCH :query
            ORDER BY rank
            """),
            {"query": search_text}
        )
        book_ids = [row[0] for row in result]

        if book_ids:
            self._query = self._query.filter(Book.id.in_(book_ids))
        else:
            # No matches - ensure query returns empty
            self._query = self._query.filter(Book.id == -1)

        return self

    def filter_by_reading_status(self, status: str) -> 'QueryBuilder':
        """Filter by reading status."""
        self._query = self._query.join(Book.personal).filter(
            PersonalMetadata.reading_status == status
        )
        return self

    def filter_by_rating(self, min_rating: int, max_rating: int = 5) -> 'QueryBuilder':
        """Filter by rating range."""
        self._query = self._query.join(Book.personal).filter(
            and_(
                PersonalMetadata.rating >= min_rating,
                PersonalMetadata.rating <= max_rating
            )
        )
        return self

    def filter_by_favorite(self, is_favorite: bool = True) -> 'QueryBuilder':
        """Filter by favorite status."""
        self._query = self._query.join(Book.personal).filter(
            PersonalMetadata.favorite == is_favorite
        )
        return self

    def filter_by_format(self, format_name: str) -> 'QueryBuilder':
        """Filter by file format (e.g., 'pdf', 'epub')."""
        from .db.models import File
        self._query = self._query.join(Book.files).filter(
            File.format.ilike(f'%{format_name}%')
        )
        return self

    def order_by(self, field: str, desc: bool = False) -> 'QueryBuilder':
        """
        Order results.

        Args:
            field: Field name (title, created_at, publication_date)
            desc: Descending order if True
        """
        field_map = {
            'title': Book.title,
            'created_at': Book.created_at,
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
