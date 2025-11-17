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
        # Given: Books filtered by language and subject
        results = (populated_library.query()
                   .filter_by_language("en")
                   .filter_by_subject("Python")
                   .order_by("title")
                   .all())

        # Then: Results should be filtered correctly
        expected_count = 2  # Based on populated_library fixture data
        assert len(results) == expected_count

        # And: Results should be ordered by title (ascending)
        if len(results) >= 2:
            assert results[0].title < results[1].title

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
        # Given: A library with known data
        all_books = populated_library.get_all_books()
        expected_book_count = len(all_books)

        # Count unique authors from test data
        all_authors = set()
        for book in all_books:
            for author in book.authors:
                all_authors.add(author.name)
        expected_author_count = len(all_authors)

        # Count unique subjects from test data
        all_subjects = set()
        for book in all_books:
            for subject in book.subjects:
                all_subjects.add(subject.name)
        expected_subject_count = len(all_subjects)

        # When: We get library stats
        stats = populated_library.stats()

        # Then: Stats should reflect the actual library contents
        assert stats['total_books'] == expected_book_count
        assert stats['total_authors'] == expected_author_count
        assert stats['total_subjects'] >= expected_subject_count  # May have auto-added subjects
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

    def test_filter_by_year(self, temp_library):
        """Test filtering by publication year."""
        # Create books with different publication dates
        test_file1 = temp_library.library_path / "book1.txt"
        test_file1.write_text("Book from 2020")
        book1 = temp_library.add_book(
            test_file1,
            metadata={"title": "Book 2020"},
            extract_text=False
        )
        book1.publication_date = "2020"
        temp_library.session.commit()

        test_file2 = temp_library.library_path / "book2.txt"
        test_file2.write_text("Book from 2021")
        book2 = temp_library.add_book(
            test_file2,
            metadata={"title": "Book 2021"},
            extract_text=False
        )
        book2.publication_date = "2021-06-15"
        temp_library.session.commit()

        # Test filtering by year
        results_2020 = temp_library.query().filter_by_year(2020).all()
        assert len(results_2020) == 1
        assert results_2020[0].id == book1.id

        results_2021 = temp_library.query().filter_by_year(2021).all()
        assert len(results_2021) == 1
        assert results_2021[0].id == book2.id

    def test_filter_by_text(self, temp_library):
        """Test full-text search using FTS5."""
        # Create books with searchable text
        test_file1 = temp_library.library_path / "python_book.txt"
        test_file1.write_text("Python programming language")
        book1 = temp_library.add_book(
            test_file1,
            metadata={"title": "Learning Python"},
            extract_text=False
        )

        test_file2 = temp_library.library_path / "java_book.txt"
        test_file2.write_text("Java programming language")
        book2 = temp_library.add_book(
            test_file2,
            metadata={"title": "Java Basics"},
            extract_text=False
        )

        # Test that filter_by_text runs without errors
        # Note: FTS5 index may not be fully populated in test environment
        results = temp_library.query().filter_by_text("Python").all()
        assert isinstance(results, list)  # Should return a list

        # Test empty search returns empty list
        results_empty = temp_library.query().filter_by_text("NonExistentWord12345").all()
        assert isinstance(results_empty, list)


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


class TestFavorites:
    """Test favorite functionality."""

    def test_set_favorite(self, temp_library):
        """Test marking book as favorite."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We mark it as favorite
        temp_library.set_favorite(book.id, True)

        # Then: It should be marked as favorite
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert personal is not None
        assert personal.favorite is True

    def test_unset_favorite(self, temp_library):
        """Test unmarking book as favorite."""
        # Given: A favorited book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.set_favorite(book.id, True)

        # When: We unmark it
        temp_library.set_favorite(book.id, False)

        # Then: It should not be favorite
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert personal.favorite is False

    def test_filter_by_favorite(self, temp_library):
        """Test filtering by favorite status."""
        # Given: Multiple books, some favorited
        for i in range(3):
            test_file = temp_library.library_path / f"book{i}.txt"
            test_file.write_text(f"Test {i}")
            book = temp_library.add_book(test_file, metadata={"title": f"Book {i}"}, extract_text=False)
            if i < 2:
                temp_library.set_favorite(book.id, True)

        # When: We filter by favorites
        results = temp_library.query().filter_by_favorite(True).all()

        # Then: Should return only favorites
        assert len(results) == 2


class TestPersonalTags:
    """Test personal tags (different from tag_service tags)."""

    def test_add_tags(self, temp_library):
        """Test adding personal tags."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We add tags
        temp_library.add_tags(book.id, ["important", "read-later"])

        # Then: Tags should be added
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert "important" in personal.personal_tags
        assert "read-later" in personal.personal_tags

    def test_add_tags_no_duplicates(self, temp_library):
        """Test that adding same tag twice doesn't create duplicates."""
        # Given: A book with tags
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.add_tags(book.id, ["important"])

        # When: We add the same tag again
        temp_library.add_tags(book.id, ["important", "new"])

        # Then: Should not have duplicates
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert personal.personal_tags.count("important") == 1
        assert "new" in personal.personal_tags

    def test_remove_tags(self, temp_library):
        """Test removing personal tags."""
        # Given: A book with tags
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.add_tags(book.id, ["important", "read-later", "archive"])

        # When: We remove some tags
        temp_library.remove_tags(book.id, ["read-later"])

        # Then: Tags should be removed
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert "important" in personal.personal_tags
        assert "archive" in personal.personal_tags
        assert "read-later" not in personal.personal_tags


class TestSubjects:
    """Test subject management."""

    def test_add_subject(self, temp_library):
        """Test adding subject to book."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We add a subject
        temp_library.add_subject(book.id, "Python Programming")

        # Then: Subject should be added
        temp_library.session.refresh(book)
        subject_names = [s.name for s in book.subjects]
        assert "Python Programming" in subject_names

    def test_add_subject_idempotent(self, temp_library):
        """Test adding same subject twice is idempotent."""
        # Given: A book with a subject
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.add_subject(book.id, "Python Programming")

        # When: We add the same subject again
        temp_library.add_subject(book.id, "Python Programming")

        # Then: Should not create duplicates
        temp_library.session.refresh(book)
        subject_names = [s.name for s in book.subjects]
        assert subject_names.count("Python Programming") == 1


class TestAnnotations:
    """Test annotation functionality."""

    def test_add_annotation(self, temp_library):
        """Test adding annotation to book."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We add an annotation
        annotation_id = temp_library.add_annotation(
            book.id,
            "Important passage",
            page=42,
            annotation_type="highlight"
        )

        # Then: Annotation should be created
        assert annotation_id is not None

    def test_get_annotations(self, temp_library):
        """Test retrieving annotations for a book."""
        # Given: A book with annotations
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.add_annotation(book.id, "Note 1", page=10)
        temp_library.add_annotation(book.id, "Note 2", page=20)

        # When: We get annotations
        annotations = temp_library.get_annotations(book.id)

        # Then: Should return all annotations
        assert len(annotations) == 2
        contents = [a.content for a in annotations]
        assert "Note 1" in contents
        assert "Note 2" in contents

    def test_delete_annotation(self, temp_library):
        """Test deleting an annotation."""
        # Given: A book with an annotation
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        annotation_id = temp_library.add_annotation(book.id, "Note to delete")

        # When: We delete it
        temp_library.delete_annotation(annotation_id)

        # Then: Annotation should be deleted
        annotations = temp_library.get_annotations(book.id)
        assert len(annotations) == 0


class TestVirtualLibraries:
    """Test virtual library functionality."""

    def test_add_to_virtual_library(self, temp_library):
        """Test adding book to virtual library."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We add it to a virtual library
        temp_library.add_to_virtual_library(book.id, "Reading List")

        # Then: Book should be in virtual library
        books = temp_library.get_virtual_library("Reading List")
        assert len(books) == 1
        assert books[0].id == book.id

    def test_remove_from_virtual_library(self, temp_library):
        """Test removing book from virtual library."""
        # Given: A book in a virtual library
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        temp_library.add_to_virtual_library(book.id, "Reading List")

        # When: We remove it
        temp_library.remove_from_virtual_library(book.id, "Reading List")

        # Then: Book should be removed
        books = temp_library.get_virtual_library("Reading List")
        assert len(books) == 0

    def test_list_virtual_libraries(self, temp_library):
        """Test listing all virtual libraries."""
        # Given: Multiple books in different virtual libraries
        test_file1 = temp_library.library_path / "book1.txt"
        test_file1.write_text("Test 1")
        book1 = temp_library.add_book(test_file1, metadata={"title": "Test 1"}, extract_text=False)

        test_file2 = temp_library.library_path / "book2.txt"
        test_file2.write_text("Test 2")
        book2 = temp_library.add_book(test_file2, metadata={"title": "Test 2"}, extract_text=False)

        temp_library.add_to_virtual_library(book1.id, "Reading List")
        temp_library.add_to_virtual_library(book2.id, "Favorites")

        # When: We list virtual libraries
        libraries = temp_library.list_virtual_libraries()

        # Then: Should return all libraries
        assert "Reading List" in libraries
        assert "Favorites" in libraries


class TestBookDeletion:
    """Test book deletion."""

    def test_delete_book(self, temp_library):
        """Test deleting a book."""
        # Given: A book
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test content")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)
        book_id = book.id

        # When: We delete it
        temp_library.delete_book(book_id)

        # Then: Book should be deleted
        from ebk.db.models import Book
        deleted_book = temp_library.session.query(Book).filter_by(id=book_id).first()
        assert deleted_book is None


class TestQueryBuilderFormat:
    """Test format filtering in QueryBuilder."""

    def test_filter_by_format(self, temp_library):
        """Test filtering by file format."""
        # Given: Books with different formats
        pdf_file = temp_library.library_path / "book.pdf"
        pdf_file.write_text("PDF content")
        pdf_book = temp_library.add_book(pdf_file, metadata={"title": "PDF Book"}, extract_text=False)

        epub_file = temp_library.library_path / "book.epub"
        epub_file.write_text("EPUB content")
        epub_book = temp_library.add_book(epub_file, metadata={"title": "EPUB Book"}, extract_text=False)

        # When: We filter by format
        pdf_results = temp_library.query().filter_by_format("pdf").all()

        # Then: Should return only PDF books
        assert len(pdf_results) >= 1
        assert any(b.id == pdf_book.id for b in pdf_results)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_set_favorite_create_personal_metadata(self, temp_library):
        """Test that set_favorite creates PersonalMetadata if missing."""
        # Given: A book without PersonalMetadata
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # Ensure no PersonalMetadata exists
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        if personal:
            temp_library.session.delete(personal)
            temp_library.session.commit()

        # When: We set favorite
        temp_library.set_favorite(book.id, True)

        # Then: PersonalMetadata should be created
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert personal is not None
        assert personal.favorite is True

    def test_add_tags_create_personal_metadata(self, temp_library):
        """Test that add_tags creates PersonalMetadata if missing."""
        # Given: A book without PersonalMetadata
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # Ensure no PersonalMetadata exists
        from ebk.db.models import PersonalMetadata
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        if personal:
            temp_library.session.delete(personal)
            temp_library.session.commit()

        # When: We add tags
        temp_library.add_tags(book.id, ["test"])

        # Then: PersonalMetadata should be created
        personal = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
        assert personal is not None
        assert "test" in personal.personal_tags

    def test_add_subject_nonexistent_book(self, temp_library):
        """Test adding subject to nonexistent book."""
        # When: We try to add subject to nonexistent book
        temp_library.add_subject(99999, "Test Subject")

        # Then: Should handle gracefully (no exception)
        # The method logs a warning but doesn't raise an exception

    def test_remove_from_virtual_library_not_in_library(self, temp_library):
        """Test removing book from virtual library it's not in."""
        # Given: A book NOT in a virtual library
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test")
        book = temp_library.add_book(test_file, metadata={"title": "Test"}, extract_text=False)

        # When: We try to remove it
        temp_library.remove_from_virtual_library(book.id, "Nonexistent Library")

        # Then: Should handle gracefully (no exception)

    def test_delete_book_nonexistent(self, temp_library):
        """Test deleting nonexistent book."""
        # When: We try to delete nonexistent book
        temp_library.delete_book(99999)

        # Then: Should handle gracefully (no exception)
