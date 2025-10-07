"""
Tests for database-backed Library API.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ebk.library_db import Library
from ebk.db.models import Book, Author, Subject


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    # Cleanup
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_library(temp_library):
    """Library with test data."""
    lib = temp_library

    # Create test files with different content (to avoid deduplication)
    test_files = []
    for i, (title, creators, subjects) in enumerate([
        ("Python Programming", ["John Doe"], ["Programming", "Python"]),
        ("Data Science Handbook", ["Jane Smith", "Bob Johnson"], ["Data Science", "Python", "Statistics"]),
        ("Machine Learning Guide", ["Alice Brown"], ["Machine Learning", "AI"])
    ]):
        test_file = lib.library_path / f"test{i}.txt"
        test_file.write_text(f"Test content for {title}")
        test_files.append(test_file)

        lib.add_book(
            test_file,
            metadata={
                "title": title,
                "creators": creators,
                "subjects": subjects,
                "language": "en",
                "publication_date": str(2020 + i)
            },
            extract_text=False,
            extract_cover=False
        )

    return lib


class TestLibraryInitialization:
    """Test library creation and initialization."""

    def test_library_creation(self):
        """Test creating a new library."""
        temp_dir = tempfile.mkdtemp()
        try:
            lib = Library.open(Path(temp_dir))
            assert lib is not None
            assert (Path(temp_dir) / "library.db").exists()
            lib.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_library_directory_structure(self, temp_library):
        """Test that library creates proper directory structure."""
        lib_path = temp_library.library_path

        assert lib_path.exists()
        assert (lib_path / "library.db").exists()


class TestBookOperations:
    """Test book CRUD operations."""

    def test_get_all_books_empty(self, temp_library):
        """Test getting books from empty library."""
        books = temp_library.get_all_books()
        assert len(books) == 0

    def test_get_all_books(self, populated_library):
        """Test getting all books."""
        books = populated_library.get_all_books()
        assert len(books) == 3

    def test_get_book_by_id(self, populated_library):
        """Test retrieving book by ID."""
        books = populated_library.get_all_books()
        book_id = books[0].id

        book = populated_library.get_book(book_id)
        assert book is not None
        assert book.id == book_id


class TestQuerying:
    """Test query builder and filtering."""

    def test_query_all(self, populated_library):
        """Test querying all books."""
        results = populated_library.query().all()
        assert len(results) == 3

    def test_filter_by_language(self, populated_library):
        """Test filtering by language."""
        results = (populated_library.query()
                   .filter_by_language("en")
                   .all())
        assert len(results) == 3

    def test_filter_by_author(self, populated_library):
        """Test filtering by author."""
        results = (populated_library.query()
                   .filter_by_author("John Doe")
                   .all())
        assert len(results) == 1
        assert results[0].title == "Python Programming"

    def test_filter_by_subject(self, populated_library):
        """Test filtering by subject."""
        results = (populated_library.query()
                   .filter_by_subject("Python")
                   .all())
        assert len(results) == 2

    def test_query_chaining(self, populated_library):
        """Test chaining multiple filters."""
        results = (populated_library.query()
                   .filter_by_language("en")
                   .filter_by_subject("Python")
                   .order_by("title")
                   .all())
        assert len(results) == 2
        assert results[0].title == "Data Science Handbook"

    def test_query_limit(self, populated_library):
        """Test query limit."""
        results = (populated_library.query()
                   .limit(2)
                   .all())
        assert len(results) == 2

    def test_query_count(self, populated_library):
        """Test query count."""
        count = (populated_library.query()
                 .filter_by_language("en")
                 .count())
        assert count == 3


class TestStatistics:
    """Test library statistics."""

    def test_stats_empty_library(self, temp_library):
        """Test stats for empty library."""
        stats = temp_library.stats()
        assert stats['total_books'] == 0
        assert stats['total_authors'] == 0
        assert stats['total_subjects'] == 0

    def test_stats_populated(self, populated_library):
        """Test stats for populated library."""
        stats = populated_library.stats()
        assert stats['total_books'] == 3
        assert stats['total_authors'] == 4  # John, Jane, Bob, Alice
        assert stats['total_subjects'] >= 5
        assert 'en' in stats['languages']


class TestTextExtraction:
    """Test text extraction functionality."""

    def test_text_extraction_creates_chunks(self, temp_library):
        """Test that text extraction creates chunks."""
        # Create a simple test file
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("This is a test book about Python programming. " * 200)

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book", "creators": ["Test Author"]},
            extract_text=True
        )

        assert book is not None
        assert len(book.files) > 0
        # Check that at least one file has extracted text
        has_extracted_text = any(f.extracted_text is not None for f in book.files)
        assert has_extracted_text
        # Check that at least one file has text chunks
        total_chunks = sum(len(f.chunks) for f in book.files)
        assert total_chunks > 0


class TestDeduplication:
    """Test hash-based deduplication."""

    def test_duplicate_file_detection(self, temp_library):
        """Test that duplicate files are detected."""
        # Create a test file
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test content for deduplication")

        # Import first time
        book1 = temp_library.add_book(
            test_file,
            metadata={"title": "First Import", "creators": ["Author"]},
            extract_text=False
        )

        # Import same file again
        book2 = temp_library.add_book(
            test_file,
            metadata={"title": "Second Import", "creators": ["Author"]},
            extract_text=False
        )

        # Should return the same book (deduplication)
        assert book1.id == book2.id

        # Should only have one file entry
        all_books = temp_library.get_all_books()
        assert len(all_books) == 1


class TestSearchFunctionality:
    """Test full-text search functionality."""

    def test_search_basic(self, temp_library):
        """Test basic full-text search."""
        # Create a book with text extraction to populate FTS index
        test_file = temp_library.library_path / "python_book.txt"
        test_file.write_text("This is a book about Python programming. " * 50)

        temp_library.add_book(
            test_file,
            metadata={
                "title": "Python Programming Guide",
                "creators": ["Author"],
                "description": "A comprehensive guide to Python"
            },
            extract_text=True
        )

        results = temp_library.search("Python")
        assert len(results) >= 1
        # Should find books with Python in title or description
        assert any("Python" in book.title for book in results)

    def test_search_with_limit(self, populated_library):
        """Test search with result limit."""
        results = populated_library.search("Python", limit=1)
        assert len(results) <= 1

    def test_search_empty_results(self, temp_library):
        """Test search with no matching results."""
        results = temp_library.search("nonexistent_term_xyz")
        assert len(results) == 0

    def test_search_empty_library(self, temp_library):
        """Test search on empty library."""
        results = temp_library.search("anything")
        assert len(results) == 0


class TestReadingStatus:
    """Test reading status management."""

    def test_update_reading_status_basic(self, populated_library):
        """Test updating reading status."""
        books = populated_library.get_all_books()
        book_id = books[0].id

        populated_library.update_reading_status(
            book_id,
            "reading",
            progress=50,
            rating=4
        )

        # Verify update
        book = populated_library.get_book(book_id)
        assert book.personal.reading_status == "reading"
        assert book.personal.reading_progress == 50
        assert book.personal.rating == 4

    def test_update_reading_status_read(self, populated_library):
        """Test marking book as read sets date."""
        books = populated_library.get_all_books()
        book_id = books[0].id

        populated_library.update_reading_status(book_id, "read")

        book = populated_library.get_book(book_id)
        assert book.personal.reading_status == "read"
        assert book.personal.date_finished is not None

    def test_update_reading_status_no_personal_metadata(self, temp_library):
        """Test updating status when no personal metadata exists."""
        # This should not crash, but won't update anything
        temp_library.update_reading_status(9999, "reading")
        # Just verify it doesn't crash


class TestBookDeletion:
    """Test book deletion functionality."""

    def test_delete_book_without_files(self, populated_library):
        """Test deleting book from database only."""
        books = populated_library.get_all_books()
        initial_count = len(books)
        book_id = books[0].id

        populated_library.delete_book(book_id, delete_files=False)

        # Book should be removed from database
        assert populated_library.get_book(book_id) is None
        assert len(populated_library.get_all_books()) == initial_count - 1

    def test_delete_book_with_files(self, temp_library):
        """Test deleting book and physical files."""
        # Create a test book
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test content")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book", "creators": ["Test Author"]},
            extract_text=False,
            extract_cover=False
        )

        book_id = book.id

        # Delete with files
        temp_library.delete_book(book_id, delete_files=True)

        # Book should be removed
        assert temp_library.get_book(book_id) is None

    def test_delete_nonexistent_book(self, temp_library):
        """Test deleting a book that doesn't exist."""
        # Should not crash
        temp_library.delete_book(9999, delete_files=False)


class TestQueryBuilderAdvanced:
    """Test advanced query builder features."""

    def test_filter_by_title_exact(self, populated_library):
        """Test exact title filtering."""
        results = (populated_library.query()
                  .filter_by_title("Python Programming", exact=True)
                  .all())
        assert len(results) == 1
        assert results[0].title == "Python Programming"

    def test_filter_by_title_partial(self, populated_library):
        """Test partial title filtering."""
        results = (populated_library.query()
                  .filter_by_title("Python")
                  .all())
        assert len(results) >= 1

    def test_filter_by_publisher(self, temp_library):
        """Test filtering by publisher."""
        # Create book with publisher
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test content")

        temp_library.add_book(
            test_file,
            metadata={
                "title": "Test Book",
                "creators": ["Author"],
                "publisher": "Test Publisher"
            },
            extract_text=False
        )

        results = (temp_library.query()
                  .filter_by_publisher("Test")
                  .all())
        assert len(results) == 1

    def test_filter_by_reading_status(self, populated_library):
        """Test filtering by reading status."""
        # Update one book's status
        books = populated_library.get_all_books()
        populated_library.update_reading_status(books[0].id, "reading")

        results = (populated_library.query()
                  .filter_by_reading_status("reading")
                  .all())
        assert len(results) >= 1

    def test_filter_by_rating(self, populated_library):
        """Test filtering by rating range."""
        books = populated_library.get_all_books()
        populated_library.update_reading_status(books[0].id, "read", rating=5)

        results = (populated_library.query()
                  .filter_by_rating(min_rating=4)
                  .all())
        assert len(results) >= 1

    def test_order_by_descending(self, populated_library):
        """Test descending order."""
        results = (populated_library.query()
                  .order_by("title", desc=True)
                  .all())
        assert len(results) >= 2
        # Verify descending order
        assert results[0].title >= results[1].title

    def test_order_by_created_at(self, populated_library):
        """Test ordering by created_at."""
        results = (populated_library.query()
                  .order_by("created_at")
                  .all())
        assert len(results) >= 1

    def test_order_by_publication_date(self, populated_library):
        """Test ordering by publication date."""
        results = (populated_library.query()
                  .order_by("publication_date")
                  .all())
        assert len(results) >= 1

    def test_offset(self, populated_library):
        """Test query offset."""
        all_results = populated_library.query().all()
        offset_results = (populated_library.query()
                         .offset(1)
                         .all())
        assert len(offset_results) == len(all_results) - 1

    def test_first(self, populated_library):
        """Test getting first result."""
        result = populated_library.query().first()
        assert result is not None
        assert isinstance(result, Book)

    def test_first_no_results(self, temp_library):
        """Test first on empty results."""
        result = (temp_library.query()
                 .filter_by_title("nonexistent")
                 .first())
        assert result is None


class TestLibraryHelperMethods:
    """Test library helper methods."""

    def test_get_book_by_unique_id(self, populated_library):
        """Test getting book by unique ID."""
        books = populated_library.get_all_books()
        unique_id = books[0].unique_id

        book = populated_library.get_book_by_unique_id(unique_id)
        assert book is not None
        assert book.unique_id == unique_id

    def test_get_book_by_unique_id_not_found(self, temp_library):
        """Test getting book with invalid unique ID."""
        book = temp_library.get_book_by_unique_id("nonexistent_id")
        assert book is None

    def test_get_books_by_author(self, populated_library):
        """Test getting books by author name."""
        books = populated_library.get_books_by_author("John")
        assert len(books) >= 1
        assert any("John" in author.name for book in books for author in book.authors)

    def test_get_books_by_subject(self, populated_library):
        """Test getting books by subject."""
        books = populated_library.get_books_by_subject("Python")
        assert len(books) >= 1
        assert any("Python" in subject.name for book in books for subject in book.subjects)

    def test_get_all_books_with_pagination(self, populated_library):
        """Test pagination in get_all_books."""
        page1 = populated_library.get_all_books(limit=2, offset=0)
        page2 = populated_library.get_all_books(limit=2, offset=2)

        assert len(page1) <= 2
        assert len(page2) <= 2
        if len(page1) > 0 and len(page2) > 0:
            assert page1[0].id != page2[0].id


class TestBatchImport:
    """Test batch import functionality."""

    def test_batch_import_without_progress(self, temp_library):
        """Test importing multiple files without progress bar."""
        files_and_metadata = []
        for i in range(3):
            test_file = temp_library.library_path / f"batch_test_{i}.txt"
            test_file.write_text(f"Test content {i}")
            files_and_metadata.append((
                test_file,
                {"title": f"Batch Book {i}", "creators": ["Batch Author"]}
            ))

        books = temp_library.batch_import(files_and_metadata, show_progress=False)
        assert len(books) == 3

    def test_batch_import_with_progress(self, temp_library):
        """Test batch import with progress bar."""
        files_and_metadata = []
        for i in range(2):
            test_file = temp_library.library_path / f"batch_progress_{i}.txt"
            test_file.write_text(f"Test content {i}")
            files_and_metadata.append((
                test_file,
                {"title": f"Progress Book {i}", "creators": ["Progress Author"]}
            ))

        books = temp_library.batch_import(files_and_metadata, show_progress=True)
        assert len(books) == 2


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_add_nonexistent_file(self, temp_library):
        """Test importing file that doesn't exist."""
        result = temp_library.add_book(
            Path("/nonexistent/file.pdf"),
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )
        assert result is None

    def test_stats_with_reading_metadata(self, populated_library):
        """Test stats with reading metadata."""
        books = populated_library.get_all_books()
        populated_library.update_reading_status(books[0].id, "read", rating=5)
        populated_library.update_reading_status(books[1].id, "reading", progress=50)

        stats = populated_library.stats()
        assert stats['read_count'] >= 1
        assert stats['reading_count'] >= 1
        assert stats['total_files'] >= 3
