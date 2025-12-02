"""
Tests for server API filter and stats features.

Tests cover:
- Reading status filter: filtering books by 'reading', 'completed', 'unread'
- Extended stats API: favorites_count, reading_count, completed_count
- JavaScript syntax validation: proper HTML entity escaping in onclick handlers
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import re

from fastapi.testclient import TestClient

from ebk.library_db import Library
from ebk.server import app, set_library


# ============================================================================
# Test Fixtures
# ============================================================================

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
def client(temp_library):
    """Create test client with library."""
    set_library(temp_library)
    return TestClient(app)


@pytest.fixture
def populated_library(temp_library):
    """Library with test books for filter tests."""
    lib = temp_library

    # Create test books with various metadata
    test_books = [
        {"title": "Python Basics", "creators": ["John Doe"], "language": "en"},
        {"title": "Advanced Python", "creators": ["Jane Smith"], "language": "en"},
        {"title": "Data Science Guide", "creators": ["Bob Johnson"], "language": "en"},
        {"title": "Machine Learning", "creators": ["Alice Brown"], "language": "en"},
        {"title": "Web Development", "creators": ["Charlie Wilson"], "language": "en"},
    ]

    for i, metadata in enumerate(test_books):
        test_file = lib.library_path / f"book{i}.txt"
        test_file.write_text(f"Content for {metadata['title']}")
        lib.add_book(test_file, metadata=metadata, extract_text=False, extract_cover=False)

    return lib


@pytest.fixture
def client_with_books(populated_library):
    """Create test client with populated library."""
    set_library(populated_library)
    return TestClient(app), populated_library


# ============================================================================
# Reading Status Filter Tests
# ============================================================================

class TestReadingStatusFilter:
    """Test filtering books by reading status via the /api/books endpoint."""

    def test_filter_by_reading_status_returns_only_books_with_that_status(self, client_with_books):
        """Test that filtering by 'reading' returns only books currently being read."""
        # Given: A library with books, one marked as 'reading'
        client, lib = client_with_books
        books = lib.get_all_books()
        target_book = books[0]
        lib.update_reading_status(target_book.id, "reading")

        # When: We filter by reading status
        response = client.get("/api/books", params={"reading_status": "reading"})

        # Then: Should return only the book being read
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["reading_status"] == "reading"
        assert data["items"][0]["id"] == target_book.id

    def test_filter_by_completed_status_returns_only_completed_books(self, client_with_books):
        """Test that filtering by 'read' returns only completed books."""
        # Given: A library with books, two marked as 'read'
        client, lib = client_with_books
        books = lib.get_all_books()
        target_book1 = books[1]
        target_book2 = books[2]
        lib.update_reading_status(target_book1.id, "read")
        lib.update_reading_status(target_book2.id, "read")

        # When: We filter by read status
        response = client.get("/api/books", params={"reading_status": "read"})

        # Then: Should return only the completed books
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        returned_ids = [item["id"] for item in data["items"]]
        assert target_book1.id in returned_ids
        assert target_book2.id in returned_ids
        # All returned books should have 'read' status
        for item in data["items"]:
            assert item["reading_status"] == "read"

    def test_filter_by_unread_status_returns_only_unread_books(self, client_with_books):
        """Test that filtering by 'unread' returns only unread books."""
        # Given: A library with books, some with other statuses
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")
        lib.update_reading_status(books[1].id, "read")
        # Books 2, 3, 4 are unread
        lib.update_reading_status(books[2].id, "unread")
        lib.update_reading_status(books[3].id, "unread")
        lib.update_reading_status(books[4].id, "unread")

        # When: We filter by unread status
        response = client.get("/api/books", params={"reading_status": "unread"})

        # Then: Should return only unread books
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_no_reading_status_filter_returns_all_books(self, client_with_books):
        """Test that without a filter, all books are returned."""
        # Given: A library with books having various statuses
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")
        lib.update_reading_status(books[1].id, "read")
        # Others remain unread by default

        # When: We list books without reading_status filter
        response = client.get("/api/books")

        # Then: Should return all books
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5

    def test_reading_status_filter_combined_with_favorite_filter(self, client_with_books):
        """Test combining reading_status with favorite filter."""
        # Given: A library with books, one is reading and favorite
        client, lib = client_with_books
        books = lib.get_all_books()
        target_book = books[0]
        other_book = books[1]
        lib.update_reading_status(target_book.id, "reading")
        lib.update_reading_status(other_book.id, "reading")
        lib.set_favorite(target_book.id, True)

        # When: We filter by both reading status and favorite
        response = client.get("/api/books", params={
            "reading_status": "reading",
            "favorite": "true"
        })

        # Then: Should return only the book that is both reading and favorite
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == target_book.id
        assert data["items"][0]["favorite"] is True
        assert data["items"][0]["reading_status"] == "reading"

    def test_reading_status_filter_combined_with_language_filter(self, client_with_books):
        """Test combining reading_status with language filter."""
        # Given: A library where all books are English, one is reading
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")

        # When: We filter by both reading status and language
        response = client.get("/api/books", params={
            "reading_status": "reading",
            "language": "en"
        })

        # Then: Should return the book
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_reading_status_filter_returns_empty_when_no_matches(self, client_with_books):
        """Test that filter returns empty list when no books match."""
        # Given: A library with no books marked as 'reading'
        client, lib = client_with_books

        # When: We filter by reading status
        response = client.get("/api/books", params={"reading_status": "reading"})

        # Then: Should return empty results
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_reading_status_filter_preserves_pagination(self, client_with_books):
        """Test that reading_status filter works correctly with pagination."""
        # Given: Multiple books with 'reading' status
        client, lib = client_with_books
        books = lib.get_all_books()
        for book in books[:3]:
            lib.update_reading_status(book.id, "reading")

        # When: We filter with pagination
        response = client.get("/api/books", params={
            "reading_status": "reading",
            "limit": 2,
            "offset": 0
        })

        # Then: Should respect pagination
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3  # Total matching
        assert len(data["items"]) == 2  # Limited to 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_reading_status_filter_works_with_sorting(self, client_with_books):
        """Test that reading_status filter works correctly with sorting."""
        # Given: Multiple books with 'read' status
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "read")
        lib.update_reading_status(books[1].id, "read")

        # When: We filter and sort by title descending
        response = client.get("/api/books", params={
            "reading_status": "read",
            "sort": "title",
            "order": "desc"
        })

        # Then: Should be sorted correctly (descending by title)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        # Verify all items have 'read' status
        for item in data["items"]:
            assert item["reading_status"] == "read"
        # Verify descending order: first title should be >= second title
        assert data["items"][0]["title"] >= data["items"][1]["title"]


# ============================================================================
# Extended Stats API Tests
# ============================================================================

class TestExtendedStatsAPI:
    """Test the extended stats endpoint with favorites_count, reading_count, completed_count."""

    def test_stats_returns_favorites_count(self, client_with_books):
        """Test that stats endpoint includes favorites_count."""
        # Given: A library with some books marked as favorite
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.set_favorite(books[0].id, True)
        lib.set_favorite(books[1].id, True)

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Should include favorites_count
        assert response.status_code == 200
        data = response.json()
        assert "favorites_count" in data
        assert data["favorites_count"] == 2

    def test_stats_returns_reading_count(self, client_with_books):
        """Test that stats endpoint includes reading_count."""
        # Given: A library with some books being read
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")
        lib.update_reading_status(books[1].id, "reading")
        lib.update_reading_status(books[2].id, "reading")

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Should include reading_count
        assert response.status_code == 200
        data = response.json()
        assert "reading_count" in data
        assert data["reading_count"] == 3

    def test_stats_returns_completed_count(self, client_with_books):
        """Test that stats endpoint includes completed_count."""
        # Given: A library with some completed books (status='read')
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "read")
        lib.update_reading_status(books[1].id, "read")

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Should include completed_count
        assert response.status_code == 200
        data = response.json()
        assert "completed_count" in data
        assert data["completed_count"] == 2

    def test_stats_counts_are_zero_for_empty_library(self, client):
        """Test that stats counts are zero when library has no books."""
        # Given: An empty library

        # When: We get stats
        response = client.get("/api/stats")

        # Then: All counts should be zero
        assert response.status_code == 200
        data = response.json()
        assert data["favorites_count"] == 0
        assert data["reading_count"] == 0
        assert data["completed_count"] == 0

    def test_stats_counts_update_after_adding_favorites(self, client_with_books):
        """Test that favorites_count updates correctly after marking favorites."""
        client, lib = client_with_books
        books = lib.get_all_books()

        # Given: Initial stats with no favorites
        response1 = client.get("/api/stats")
        assert response1.status_code == 200
        initial_favorites = response1.json()["favorites_count"]

        # When: We mark a book as favorite
        lib.set_favorite(books[0].id, True)

        # Then: Favorites count should increase
        response2 = client.get("/api/stats")
        assert response2.status_code == 200
        assert response2.json()["favorites_count"] == initial_favorites + 1

    def test_stats_counts_update_after_changing_reading_status(self, client_with_books):
        """Test that reading_count and completed_count update correctly."""
        client, lib = client_with_books
        books = lib.get_all_books()

        # Given: Initial stats
        response1 = client.get("/api/stats")
        assert response1.status_code == 200
        initial_reading = response1.json()["reading_count"]
        initial_completed = response1.json()["completed_count"]

        # When: We mark a book as reading
        lib.update_reading_status(books[0].id, "reading")

        # Then: Reading count should increase
        response2 = client.get("/api/stats")
        assert response2.status_code == 200
        assert response2.json()["reading_count"] == initial_reading + 1

        # When: We mark the same book as read
        lib.update_reading_status(books[0].id, "read")

        # Then: Completed count should increase, reading count should decrease
        response3 = client.get("/api/stats")
        assert response3.status_code == 200
        assert response3.json()["completed_count"] == initial_completed + 1
        assert response3.json()["reading_count"] == initial_reading  # Back to initial

    def test_stats_includes_all_expected_fields(self, client_with_books):
        """Test that stats endpoint returns all expected fields."""
        client, _ = client_with_books

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Should include all expected fields
        assert response.status_code == 200
        data = response.json()

        expected_fields = [
            "total_books",
            "total_authors",
            "total_subjects",
            "total_files",
            "total_size_mb",
            "languages",
            "formats",
            "favorites_count",
            "reading_count",
            "completed_count"
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_stats_returns_correct_total_books(self, client_with_books):
        """Test that total_books count is accurate."""
        client, lib = client_with_books

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Total books should match
        assert response.status_code == 200
        data = response.json()
        assert data["total_books"] == 5

    def test_stats_favorites_count_decreases_when_unfavoriting(self, client_with_books):
        """Test that favorites_count decreases when unfavoriting a book."""
        client, lib = client_with_books
        books = lib.get_all_books()

        # Given: A book marked as favorite
        lib.set_favorite(books[0].id, True)
        response1 = client.get("/api/stats")
        initial_favorites = response1.json()["favorites_count"]

        # When: We unfavorite the book
        lib.set_favorite(books[0].id, False)

        # Then: Favorites count should decrease
        response2 = client.get("/api/stats")
        assert response2.json()["favorites_count"] == initial_favorites - 1


# ============================================================================
# JavaScript Syntax Validation Tests
# ============================================================================

class TestJavaScriptSyntaxValidation:
    """Test that generated HTML contains valid JavaScript syntax."""

    def test_onclick_handlers_use_html_entity_escaping(self, client):
        """Test that onclick handlers use HTML entity escaping for quotes."""
        # When: We get the main page HTML
        response = client.get("/")

        # Then: Should return HTML
        assert response.status_code == 200
        html = response.text

        # Check for the specific pattern with &apos; entity escaping
        # The showImportResults function should use &apos; for onclick handlers
        assert "&apos;" in html, "HTML should contain &apos; entity for quote escaping"

    def test_import_results_button_uses_entity_escaping(self, client):
        """Test that showImportResults function uses HTML entity escaping."""
        # When: We get the main page HTML
        response = client.get("/")

        # Then: The showImportResults function should use &apos; for the Done button
        assert response.status_code == 200
        html = response.text

        # The specific fix was for the Done button in showImportResults
        # It should use: closeModal(&apos;import-modal&apos;)
        # NOT: closeModal(\'import-modal\')
        assert "closeModal(&apos;import-modal&apos;)" in html, \
            "showImportResults Done button should use &apos; entity escaping"

    def test_html_contains_valid_onclick_with_entity_escaping(self, client):
        """Test that HTML contains properly escaped onclick handlers."""
        # When: We get the main page HTML
        response = client.get("/")

        # Then: Should contain properly escaped onclick handlers
        assert response.status_code == 200
        html = response.text

        # The correct pattern uses &apos; for single quotes in onclick
        # onclick="closeModal(&apos;import-modal&apos;)"
        valid_pattern = r"onclick=\"[^\"]*&apos;[^\"]*&apos;[^\"]*\""
        matches = re.findall(valid_pattern, html)

        assert len(matches) > 0, "HTML should contain onclick handlers with &apos; entity escaping"

    def test_closemodal_function_call_is_properly_escaped(self, client):
        """Test that closeModal function calls are properly escaped in HTML."""
        # When: We get the main page HTML
        response = client.get("/")

        # Then: Should contain properly formatted closeModal calls
        assert response.status_code == 200
        html = response.text

        # Check for closeModal with proper entity escaping
        assert "closeModal(&apos;" in html, "closeModal should use &apos; for argument quotes"


# ============================================================================
# Integration Tests - Reading Status Filter with Stats
# ============================================================================

class TestReadingStatusFilterWithStats:
    """Integration tests verifying filter and stats work together correctly."""

    def test_filtered_count_matches_stats_reading_count(self, client_with_books):
        """Test that filtered count for 'reading' matches stats reading_count."""
        # Given: A library with some books being read
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")
        lib.update_reading_status(books[1].id, "reading")

        # When: We get both stats and filtered books
        stats_response = client.get("/api/stats")
        books_response = client.get("/api/books", params={"reading_status": "reading"})

        # Then: Counts should match
        assert stats_response.status_code == 200
        assert books_response.status_code == 200

        stats_data = stats_response.json()
        books_data = books_response.json()

        assert stats_data["reading_count"] == books_data["total"]

    def test_filtered_count_matches_stats_completed_count(self, client_with_books):
        """Test that filtered count for 'read' matches stats completed_count."""
        # Given: A library with some completed books
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "read")
        lib.update_reading_status(books[1].id, "read")
        lib.update_reading_status(books[2].id, "read")

        # When: We get both stats and filtered books
        stats_response = client.get("/api/stats")
        books_response = client.get("/api/books", params={"reading_status": "read"})

        # Then: Counts should match
        assert stats_response.status_code == 200
        assert books_response.status_code == 200

        stats_data = stats_response.json()
        books_data = books_response.json()

        assert stats_data["completed_count"] == books_data["total"]

    def test_all_statuses_sum_equals_total_books(self, client_with_books):
        """Test that sum of all reading status counts equals total books."""
        # Given: A library with books in different statuses
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")
        lib.update_reading_status(books[1].id, "read")
        lib.update_reading_status(books[2].id, "unread")
        lib.update_reading_status(books[3].id, "unread")
        lib.update_reading_status(books[4].id, "unread")

        # When: We get counts for each status
        reading_response = client.get("/api/books", params={"reading_status": "reading"})
        read_response = client.get("/api/books", params={"reading_status": "read"})
        unread_response = client.get("/api/books", params={"reading_status": "unread"})
        stats_response = client.get("/api/stats")

        # Then: Sum should equal total
        reading_count = reading_response.json()["total"]
        read_count = read_response.json()["total"]
        unread_count = unread_response.json()["total"]
        total_books = stats_response.json()["total_books"]

        assert reading_count + read_count + unread_count == total_books


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_reading_status_value_returns_empty_results(self, client_with_books):
        """Test that an invalid reading status value returns empty results."""
        # Given: A populated library
        client, _ = client_with_books

        # When: We filter with an invalid status
        response = client.get("/api/books", params={"reading_status": "invalid_status"})

        # Then: Should return empty results (no books match)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_empty_string_reading_status_is_ignored(self, client_with_books):
        """Test that empty string for reading_status is treated as no filter."""
        # Given: A populated library
        client, _ = client_with_books

        # When: We filter with empty reading status
        # Note: FastAPI may treat empty string as None or empty
        response = client.get("/api/books", params={"reading_status": ""})

        # Then: Should return all books (filter ignored)
        assert response.status_code == 200
        data = response.json()
        # Empty string should be treated as no filter, returning all books
        assert data["total"] == 5

    def test_reading_status_filter_case_sensitive(self, client_with_books):
        """Test that reading status filter is case sensitive."""
        # Given: A library with a book marked as 'reading'
        client, lib = client_with_books
        books = lib.get_all_books()
        lib.update_reading_status(books[0].id, "reading")

        # When: We filter with uppercase 'READING'
        response = client.get("/api/books", params={"reading_status": "READING"})

        # Then: Should return no results (case sensitive)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_stats_handles_books_without_personal_metadata(self, client_with_books):
        """Test that stats work correctly when some books lack personal metadata."""
        # Given: A populated library (some books may not have personal metadata)
        client, _ = client_with_books

        # When: We get stats
        response = client.get("/api/stats")

        # Then: Should not crash and return valid stats
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["favorites_count"], int)
        assert isinstance(data["reading_count"], int)
        assert isinstance(data["completed_count"], int)
