"""
Tests for database models and session management.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ebk.library_db import Library
from ebk.db.models import Book, Author, Subject, File, ExtractedText, Cover
from ebk.db.session import init_db, get_session, close_db, session_scope, get_or_create


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    # Cleanup
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestBookModel:
    """Test Book model functionality."""

    def test_book_creation(self, temp_library):
        """Test creating a book."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test content")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book", "creators": ["Author"]},
            extract_text=False
        )

        assert book.id is not None
        assert book.title == "Test Book"
        assert book.unique_id is not None
        assert book.created_at is not None

    def test_book_primary_file(self, temp_library):
        """Test primary_file hybrid property."""
        test_file1 = temp_library.library_path / "test.epub"
        test_file1.write_text("EPUB content")

        book = temp_library.add_book(
            test_file1,
            metadata={"title": "Multi-format Book", "creators": ["Author"]},
            extract_text=False
        )

        # Add PDF file (higher priority)
        test_file2 = temp_library.library_path / "test.pdf"
        test_file2.write_text("PDF content - different")

        temp_library.add_book(
            test_file2,
            metadata={"title": "Multi-format Book", "creators": ["Author"]},
            extract_text=False
        )

        # Refresh book
        book = temp_library.get_book(book.id)

        # PDF should be primary
        primary = book.primary_file
        assert primary is not None
        assert primary.format == "pdf"

    def test_book_primary_file_no_files(self, temp_library):
        """Test primary_file when book has no files."""
        # Create book directly in database without files
        book = Book(
            unique_id="test123",
            title="No Files Book",
            language="en"
        )
        temp_library.session.add(book)
        temp_library.session.commit()

        primary = book.primary_file
        assert primary is None

    def test_book_primary_cover(self, temp_library):
        """Test primary_cover hybrid property."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        # Add covers manually
        cover1 = Cover(
            book_id=book.id,
            path="covers/cover1.jpg",
            width=200,
            height=300,
            is_primary=False
        )
        cover2 = Cover(
            book_id=book.id,
            path="covers/cover2.jpg",
            width=200,
            height=300,
            is_primary=True
        )

        temp_library.session.add_all([cover1, cover2])
        temp_library.session.commit()

        # Refresh
        book = temp_library.get_book(book.id)

        primary = book.primary_cover
        assert primary is not None
        assert primary.is_primary == True

    def test_book_primary_cover_no_covers(self, temp_library):
        """Test primary_cover when book has no covers."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False,
            extract_cover=False
        )

        primary = book.primary_cover
        assert primary is None

    def test_book_can_be_inspected(self, temp_library):
        """Test that book objects can be inspected and debugged."""
        # Given: A book in the library
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book Title", "creators": ["Author"]},
            extract_text=False
        )

        # When: We inspect the book object
        repr_str = repr(book)

        # Then: It should provide useful debugging information
        assert repr_str is not None
        assert len(repr_str) > 0
        assert isinstance(repr_str, str)


class TestFileModel:
    """Test File model functionality."""

    def test_file_compute_hash(self, temp_library):
        """Test File.compute_hash static method."""
        test_file = temp_library.library_path / "test.txt"
        content = "Test content for hashing"
        test_file.write_text(content)

        file_hash = File.compute_hash(test_file)

        assert len(file_hash) == 64  # SHA256
        assert isinstance(file_hash, str)

        # Verify deterministic
        file_hash2 = File.compute_hash(test_file)
        assert file_hash == file_hash2

    def test_file_can_be_inspected(self, temp_library):
        """Test that file objects can be inspected and debugged."""
        # Given: A book with a file
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        # When: We inspect the file object
        file = book.files[0]
        repr_str = repr(file)

        # Then: It should provide useful debugging information
        assert repr_str is not None
        assert len(repr_str) > 0
        assert isinstance(repr_str, str)


class TestAuthorModel:
    """Test Author model."""

    def test_author_can_be_inspected(self, temp_library):
        """Test that author objects can be inspected and debugged."""
        # Given: A book with an author
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["John Doe"]},
            extract_text=False
        )

        # When: We inspect the author object
        author = book.authors[0]
        repr_str = repr(author)

        # Then: It should provide useful debugging information
        assert repr_str is not None
        assert len(repr_str) > 0
        assert isinstance(repr_str, str)


class TestSubjectModel:
    """Test Subject model."""

    def test_subject_can_be_inspected(self, temp_library):
        """Test that subject objects can be inspected and debugged."""
        # Given: A book with a subject
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"], "subjects": ["Programming"]},
            extract_text=False
        )

        # When: We inspect the subject object
        subject = book.subjects[0]
        repr_str = repr(subject)

        # Then: It should provide useful debugging information
        assert repr_str is not None
        assert len(repr_str) > 0
        assert isinstance(repr_str, str)


class TestExtractedTextModel:
    """Test ExtractedText model."""

    def test_extracted_text_can_be_inspected(self, temp_library):
        """Test that extracted text objects can be inspected and debugged."""
        # Given: A book with extracted text
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("This is a test book. " * 50)  # Make it long enough

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=True
        )

        # When: We inspect the extracted text object
        file = book.files[0]
        extracted = file.extracted_text

        # Then: It should provide useful debugging information if text was extracted
        if extracted:
            repr_str = repr(extracted)
            assert repr_str is not None
            assert len(repr_str) > 0
            assert isinstance(repr_str, str)


class TestCoverModel:
    """Test Cover model."""

    def test_cover_can_be_inspected(self, temp_library):
        """Test that cover objects can be inspected and debugged."""
        # Given: A book with a cover
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        cover = Cover(
            book_id=book.id,
            path="covers/test.jpg",
            width=200,
            height=300,
            is_primary=True
        )

        temp_library.session.add(cover)
        temp_library.session.commit()

        # When: We inspect the cover object
        repr_str = repr(cover)

        # Then: It should provide useful debugging information
        assert repr_str is not None
        assert len(repr_str) > 0
        assert isinstance(repr_str, str)


class TestSessionManagement:
    """Test database session management."""

    def test_init_db(self):
        """Test database initialization."""
        temp_dir = tempfile.mkdtemp()
        try:
            engine = init_db(Path(temp_dir), echo=False)
            assert engine is not None

            # Check database file exists
            db_path = Path(temp_dir) / "library.db"
            assert db_path.exists()

            close_db()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_session_before_init(self):
        """Test getting session before initialization."""
        # Reset global state
        close_db()

        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_session()

    def test_session_scope_success(self):
        """Test session_scope context manager with success."""
        temp_dir = tempfile.mkdtemp()
        try:
            init_db(Path(temp_dir))

            with session_scope() as session:
                book = Book(
                    unique_id="test123",
                    title="Test Book",
                    language="en"
                )
                session.add(book)
                # Should auto-commit

            # Verify book was saved
            with session_scope() as session:
                saved_book = session.query(Book).filter_by(unique_id="test123").first()
                assert saved_book is not None
                assert saved_book.title == "Test Book"

            close_db()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_session_scope_rollback(self):
        """Test session_scope rolls back on error."""
        temp_dir = tempfile.mkdtemp()
        try:
            init_db(Path(temp_dir))

            with pytest.raises(ValueError):
                with session_scope() as session:
                    book = Book(
                        unique_id="test456",
                        title="Test Book",
                        language="en"
                    )
                    session.add(book)
                    session.flush()
                    raise ValueError("Test error")

            # Verify book was NOT saved (rolled back)
            with session_scope() as session:
                saved_book = session.query(Book).filter_by(unique_id="test456").first()
                assert saved_book is None

            close_db()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_or_create_existing(self, temp_library):
        """Test get_or_create with existing entity."""
        # Create author
        author1, created1 = get_or_create(
            temp_library.session,
            Author,
            name="John Doe",
            sort_name="Doe, John"
        )

        assert created1 == True
        assert author1.name == "John Doe"

        # Get same author
        author2, created2 = get_or_create(
            temp_library.session,
            Author,
            name="John Doe",
            sort_name="Doe, John"
        )

        assert created2 == False
        assert author1.id == author2.id

    def test_get_or_create_new(self, temp_library):
        """Test get_or_create with new entity."""
        subject, created = get_or_create(
            temp_library.session,
            Subject,
            name="New Subject",
            type="topic"
        )

        assert created == True
        assert subject.name == "New Subject"

    def test_close_db(self):
        """Test database cleanup."""
        temp_dir = tempfile.mkdtemp()
        try:
            init_db(Path(temp_dir))
            session = get_session()
            assert session is not None

            close_db()

            # Should raise error after close
            with pytest.raises(RuntimeError):
                get_session()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRelationships:
    """Test model relationships."""

    def test_book_authors_relationship(self, temp_library):
        """Test many-to-many book-authors relationship."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={
                "title": "Multi-author Book",
                "creators": ["Author One", "Author Two", "Author Three"]
            },
            extract_text=False
        )

        assert len(book.authors) == 3
        author_names = {a.name for a in book.authors}
        assert "Author One" in author_names
        assert "Author Two" in author_names
        assert "Author Three" in author_names

    def test_book_subjects_relationship(self, temp_library):
        """Test many-to-many book-subjects relationship."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={
                "title": "Test Book",
                "creators": ["Author"],
                "subjects": ["Subject1", "Subject2", "Subject3"]
            },
            extract_text=False
        )

        assert len(book.subjects) >= 3
        subject_names = {s.name for s in book.subjects}
        assert "Subject1" in subject_names
        assert "Subject2" in subject_names

    def test_book_files_cascade_delete(self, temp_library):
        """Test that deleting book cascades to files."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file_id = book.files[0].id

        # Delete book
        temp_library.session.delete(book)
        temp_library.session.commit()

        # File should be deleted
        file = temp_library.session.query(File).get(file_id)
        assert file is None

    def test_book_personal_metadata_relationship(self, temp_library):
        """Test book-personal metadata one-to-one relationship."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        assert book.personal is not None
        assert book.personal.reading_status == "unread"
        assert book.personal.owned == True
