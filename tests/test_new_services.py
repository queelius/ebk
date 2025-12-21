"""
Tests for new ebk services: Queue, PersonalMetadata, Annotation, Export.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ebk.library_db import Library
from ebk.services import (
    ReadingQueueService,
    PersonalMetadataService,
    AnnotationService,
    ExportService,
    ViewService,
)
from ebk.db.models import Book, PersonalMetadata, Annotation


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def library_with_books(temp_library):
    """Create a library with some test books."""
    # Add some test books
    for i in range(5):
        book = Book(
            unique_id=f"test-book-{i}",
            title=f"Test Book {i}",
            language="en",
        )
        temp_library.session.add(book)
    temp_library.session.flush()  # Get IDs assigned

    # Now create personal metadata with valid book IDs
    for book in temp_library.session.query(Book).all():
        pm = PersonalMetadata(book_id=book.id)
        temp_library.session.add(pm)
    temp_library.session.commit()

    # Refresh to get all data
    books = temp_library.session.query(Book).all()
    yield temp_library, books


# =============================================================================
# ReadingQueueService Tests
# =============================================================================

class TestReadingQueueService:
    """Tests for the ReadingQueueService."""

    def test_add_to_queue(self, library_with_books):
        """Test adding a book to the queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        position = svc.add(books[0].id)
        assert position == 1

        queue = svc.get_queue()
        assert len(queue) == 1
        assert queue[0].id == books[0].id

    def test_add_to_queue_at_position(self, library_with_books):
        """Test adding a book at a specific position."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id, position=1)

        queue = svc.get_queue()
        assert len(queue) == 2
        assert queue[0].id == books[1].id
        assert queue[1].id == books[0].id

    def test_remove_from_queue(self, library_with_books):
        """Test removing a book from the queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id)

        result = svc.remove(books[0].id)
        assert result is True

        queue = svc.get_queue()
        assert len(queue) == 1
        assert queue[0].id == books[1].id

    def test_reorder_queue(self, library_with_books):
        """Test reordering items in the queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id)
        svc.add(books[2].id)

        svc.reorder(books[2].id, 1)

        queue = svc.get_queue()
        assert queue[0].id == books[2].id
        assert queue[1].id == books[0].id
        assert queue[2].id == books[1].id

    def test_get_next(self, library_with_books):
        """Test getting the next book in queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id)

        next_book = svc.get_next()
        assert next_book.id == books[0].id

    def test_clear_queue(self, library_with_books):
        """Test clearing the entire queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id)

        count = svc.clear()
        assert count == 2
        assert svc.count() == 0

    def test_is_in_queue(self, library_with_books):
        """Test checking if a book is in the queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)

        assert svc.is_in_queue(books[0].id) is True
        assert svc.is_in_queue(books[1].id) is False

    def test_pop_next(self, library_with_books):
        """Test popping the next book from queue."""
        lib, books = library_with_books
        svc = ReadingQueueService(lib.session)

        svc.add(books[0].id)
        svc.add(books[1].id)

        popped = svc.pop_next()
        assert popped.id == books[0].id
        assert svc.count() == 1


# =============================================================================
# PersonalMetadataService Tests
# =============================================================================

class TestPersonalMetadataService:
    """Tests for the PersonalMetadataService."""

    def test_set_rating(self, library_with_books):
        """Test setting a book rating."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        pm = svc.set_rating(books[0].id, 4.5)
        assert pm.rating == 4.5

    def test_set_rating_invalid(self, library_with_books):
        """Test that invalid ratings are rejected."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        with pytest.raises(ValueError):
            svc.set_rating(books[0].id, 6)

        with pytest.raises(ValueError):
            svc.set_rating(books[0].id, -1)

    def test_set_favorite(self, library_with_books):
        """Test marking a book as favorite."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        pm = svc.set_favorite(books[0].id, True)
        assert pm.favorite is True

        pm = svc.set_favorite(books[0].id, False)
        assert pm.favorite is False

    def test_set_reading_status(self, library_with_books):
        """Test setting reading status."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        pm = svc.set_reading_status(books[0].id, 'reading')
        assert pm.reading_status == 'reading'
        assert pm.date_started is not None

        pm = svc.set_reading_status(books[0].id, 'read')
        assert pm.reading_status == 'read'
        assert pm.date_finished is not None
        assert pm.reading_progress == 100

    def test_set_reading_status_invalid(self, library_with_books):
        """Test that invalid status is rejected."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        with pytest.raises(ValueError):
            svc.set_reading_status(books[0].id, 'invalid_status')

    def test_update_progress(self, library_with_books):
        """Test updating reading progress."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        pm = svc.update_progress(books[0].id, 50)
        assert pm.reading_progress == 50
        assert pm.reading_status == 'reading'

    def test_get_favorites(self, library_with_books):
        """Test getting all favorite books."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        svc.set_favorite(books[0].id, True)
        svc.set_favorite(books[2].id, True)

        favorites = svc.get_favorites()
        assert len(favorites) == 2

    def test_get_by_status(self, library_with_books):
        """Test getting books by reading status."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        svc.set_reading_status(books[0].id, 'reading')
        svc.set_reading_status(books[1].id, 'reading')
        svc.set_reading_status(books[2].id, 'read')

        reading = svc.get_by_status('reading')
        assert len(reading) == 2

    def test_add_personal_tags(self, library_with_books):
        """Test adding personal tags."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        pm = svc.add_personal_tags(books[0].id, ['sci-fi', 'favorite'])
        assert 'sci-fi' in pm.personal_tags
        assert 'favorite' in pm.personal_tags

    def test_get_stats(self, library_with_books):
        """Test getting personal metadata statistics."""
        lib, books = library_with_books
        svc = PersonalMetadataService(lib.session)

        svc.set_favorite(books[0].id, True)
        svc.set_rating(books[1].id, 5)
        svc.set_reading_status(books[2].id, 'read')

        stats = svc.get_stats()
        assert stats['favorites_count'] == 1
        assert 'by_status' in stats
        assert 'by_rating' in stats


# =============================================================================
# AnnotationService Tests
# =============================================================================

class TestAnnotationService:
    """Tests for the AnnotationService."""

    def test_create_annotation(self, library_with_books):
        """Test creating an annotation."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        annotation = svc.create(
            books[0].id,
            content="This is a test note",
            annotation_type='note',
            page_number=42
        )

        assert annotation.id is not None
        assert annotation.content == "This is a test note"
        assert annotation.page_number == 42

    def test_list_annotations(self, library_with_books):
        """Test listing annotations for a book."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        svc.create(books[0].id, "Note 1", page_number=1)
        svc.create(books[0].id, "Note 2", page_number=2)
        svc.create(books[0].id, "Highlight", annotation_type='highlight', page_number=3)

        annotations = svc.list(books[0].id)
        assert len(annotations) == 3

        notes_only = svc.list(books[0].id, type_filter='note')
        assert len(notes_only) == 2

    def test_update_annotation(self, library_with_books):
        """Test updating an annotation."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        annotation = svc.create(books[0].id, "Original content")
        updated = svc.update(annotation.id, content="Updated content")

        assert updated.content == "Updated content"

    def test_delete_annotation(self, library_with_books):
        """Test deleting an annotation."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        annotation = svc.create(books[0].id, "To be deleted")
        result = svc.delete(annotation.id)

        assert result is True
        assert svc.get(annotation.id) is None

    def test_delete_all_for_book(self, library_with_books):
        """Test deleting all annotations for a book."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        svc.create(books[0].id, "Note 1")
        svc.create(books[0].id, "Note 2")
        svc.create(books[1].id, "Other book note")

        count = svc.delete_all_for_book(books[0].id)
        assert count == 2
        assert svc.count(books[0].id) == 0
        assert svc.count(books[1].id) == 1

    def test_export_json(self, library_with_books):
        """Test exporting annotations as JSON."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        svc.create(books[0].id, "Test note", page_number=1)

        json_output = svc.export(books[0].id, format_type='json')
        data = json.loads(json_output)

        assert 'annotations' in data
        assert len(data['annotations']) == 1

    def test_export_markdown(self, library_with_books):
        """Test exporting annotations as Markdown."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        svc.create(books[0].id, "Test note", page_number=1)

        md_output = svc.export(books[0].id, format_type='markdown')
        assert '# Annotations' in md_output

    def test_count_by_type(self, library_with_books):
        """Test counting annotations by type."""
        lib, books = library_with_books
        svc = AnnotationService(lib.session, lib.library_path)

        svc.create(books[0].id, "Note 1", annotation_type='note')
        svc.create(books[0].id, "Note 2", annotation_type='note')
        svc.create(books[0].id, "Highlight", annotation_type='highlight')

        counts = svc.count_by_type(books[0].id)
        assert counts.get('note', 0) == 2
        assert counts.get('highlight', 0) == 1


# =============================================================================
# ExportService Tests
# =============================================================================

class TestExportService:
    """Tests for the ExportService."""

    def test_export_json(self, library_with_books):
        """Test exporting books to JSON."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        json_output = svc.export_json(books)
        data = json.loads(json_output)

        assert 'books' in data
        assert len(data['books']) == 5

    def test_export_json_with_options(self, library_with_books):
        """Test export JSON with different options."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        json_output = svc.export_json(
            books,
            include_annotations=False,
            include_personal=False,
            pretty=False
        )

        assert '\n' not in json_output  # Not pretty-printed

    def test_export_csv(self, library_with_books):
        """Test exporting books to CSV."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        csv_output = svc.export_csv(books)
        lines = csv_output.strip().split('\n')

        # Header + 5 books
        assert len(lines) == 6
        assert 'title' in lines[0].lower()

    def test_export_csv_custom_fields(self, library_with_books):
        """Test CSV export with custom fields."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        csv_output = svc.export_csv(books, fields=['id', 'title'])
        header = csv_output.split('\n')[0]

        assert 'id' in header
        assert 'title' in header
        assert 'authors' not in header

    def test_export_html(self, library_with_books):
        """Test exporting books to HTML."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = Path(f.name)

        try:
            stats = svc.export_html(books, output_path)

            assert output_path.exists()
            assert stats['books'] == 5

            content = output_path.read_text()
            assert 'Test Book' in content
        finally:
            output_path.unlink(missing_ok=True)

    def test_get_views_data(self, library_with_books):
        """Test getting views data for export."""
        lib, books = library_with_books
        svc = ExportService(lib.session, lib.library_path)

        views_data = svc.get_views_data(books)

        # Should at least have built-in views
        assert isinstance(views_data, list)


# =============================================================================
# ViewService Integration Tests
# =============================================================================

class TestViewServiceIntegration:
    """Integration tests for ViewService via services layer."""

    def test_import_view_service(self):
        """Test that ViewService is accessible via services layer."""
        from ebk.services import ViewService
        assert ViewService is not None

    def test_view_service_basic(self, library_with_books):
        """Test basic ViewService operations."""
        lib, books = library_with_books
        svc = ViewService(lib.session)

        # List views (should include builtins)
        views = svc.list(include_builtin=True)
        assert len(views) > 0

        # Create a view
        view = svc.create('test-view', description='Test view')
        assert view.name == 'test-view'

        # Delete it
        result = svc.delete('test-view')
        assert result is True
