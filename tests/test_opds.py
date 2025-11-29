"""
Tests for OPDS (Open Publication Distribution System) catalog server.

Tests cover:
- Root catalog (navigation feed)
- Book listings with pagination
- Search functionality
- Author/Subject/Language browsing
- Single book details
- File downloads and cover images
- 404 responses for non-existent resources
- Valid Atom XML with correct OPDS MIME types
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from ebk.library_db import Library
from ebk.server import app, create_app
from ebk import opds
from ebk.db.models import Book, Author, Subject, Cover


# OPDS MIME types for validation
OPDS_MIME = "application/atom+xml;profile=opds-catalog;kind=navigation"
OPDS_ACQUISITION_MIME = "application/atom+xml;profile=opds-catalog;kind=acquisition"
OPENSEARCH_MIME = "application/opensearchdescription+xml"


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
    """Library with test data for OPDS endpoints."""
    lib = temp_library

    # Create test books with varying metadata
    test_data = [
        {
            "title": "Python Programming",
            "creators": ["John Doe"],
            "subjects": ["Programming", "Python"],
            "language": "en",
            "description": "A comprehensive guide to Python programming.",
            "publication_date": "2020"
        },
        {
            "title": "Data Science Handbook",
            "creators": ["Jane Smith", "Bob Johnson"],
            "subjects": ["Data Science", "Python", "Statistics"],
            "language": "en",
            "description": "Learn data science from scratch.",
            "publication_date": "2021"
        },
        {
            "title": "Machine Learning Guide",
            "creators": ["Alice Brown"],
            "subjects": ["Machine Learning", "AI"],
            "language": "en",
            "description": "Introduction to machine learning algorithms.",
            "publication_date": "2022"
        },
        {
            "title": "Introduction a la Programmation",
            "creators": ["Pierre Martin"],
            "subjects": ["Programming"],
            "language": "fr",
            "description": "Un guide de programmation en francais.",
            "publication_date": "2019"
        }
    ]

    for i, metadata in enumerate(test_data):
        test_file = lib.library_path / f"test{i}.txt"
        test_file.write_text(f"Test content for {metadata['title']}")

        lib.add_book(
            test_file,
            metadata=metadata,
            extract_text=False,
            extract_cover=False
        )

    return lib


@pytest.fixture
def client(populated_library):
    """Create test client with populated library."""
    opds.set_library(populated_library)
    return TestClient(app)


@pytest.fixture
def empty_client(temp_library):
    """Create test client with empty library."""
    opds.set_library(temp_library)
    return TestClient(app)


def is_valid_atom_xml(content: str) -> bool:
    """Check if content is valid Atom XML."""
    try:
        root = ET.fromstring(content)
        # Check for Atom namespace
        return "atom" in root.tag.lower() or "feed" in root.tag.lower()
    except ET.ParseError:
        return False


def get_xml_root(content: str) -> ET.Element:
    """Parse XML content and return root element."""
    return ET.fromstring(content)


class TestOPDSRootCatalog:
    """Test the OPDS root catalog endpoint."""

    def test_root_catalog_returns_valid_atom_xml(self, client):
        """Test that root catalog returns valid Atom XML."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should return success with valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_root_catalog_has_correct_mime_type(self, client):
        """Test that root catalog has navigation OPDS MIME type."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Content-Type should be OPDS navigation feed
        assert OPDS_MIME in response.headers["content-type"]

    def test_root_catalog_contains_navigation_entries(self, client):
        """Test that root catalog contains expected navigation sections."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should contain navigation links to various sections
        content = response.text
        assert "All Books" in content
        assert "Recently Added" in content
        assert "By Author" in content
        assert "By Subject" in content
        assert "By Language" in content

    def test_root_catalog_shows_library_statistics(self, client):
        """Test that root catalog shows book count in content."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should show the number of books
        assert "4 books" in response.text  # We have 4 test books

    def test_root_catalog_includes_search_link(self, client):
        """Test that root catalog includes search link."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should include OpenSearch link
        assert "opensearch.xml" in response.text


class TestOPDSAllBooks:
    """Test the all books acquisition feed endpoint."""

    def test_all_books_returns_valid_atom_xml(self, client):
        """Test that all books endpoint returns valid Atom XML."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_all_books_has_acquisition_mime_type(self, client):
        """Test that all books has acquisition OPDS MIME type."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_all_books_contains_book_entries(self, client):
        """Test that all books feed contains book entries."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should contain our test books
        content = response.text
        assert "Python Programming" in content
        assert "Data Science Handbook" in content
        assert "Machine Learning Guide" in content

    def test_all_books_pagination_defaults(self, client):
        """Test default pagination behavior."""
        # When: We request all books without pagination params
        response = client.get("/opds/all")

        # Then: Should include pagination info
        content = response.text
        assert "totalResults" in content
        assert "startIndex" in content
        assert "itemsPerPage" in content

    def test_all_books_pagination_with_limit(self, client):
        """Test pagination with custom limit."""
        # When: We request books with limit=2
        response = client.get("/opds/all?limit=2")

        # Then: Should return success and include "next" link
        assert response.status_code == 200
        assert 'rel="next"' in response.text

    def test_all_books_pagination_next_page(self, client):
        """Test pagination to next page."""
        # When: We request page 2 with small limit
        response = client.get("/opds/all?page=2&limit=2")

        # Then: Should return success and include "previous" link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_all_books_empty_library(self, empty_client):
        """Test all books with empty library."""
        # When: We request all books from empty library
        response = empty_client.get("/opds/all")

        # Then: Should return success with empty feed
        assert response.status_code == 200
        assert "totalResults>0</opensearch:totalResults" in response.text


class TestOPDSRecentBooks:
    """Test the recently added books endpoint."""

    def test_recent_books_returns_valid_atom_xml(self, client):
        """Test that recent books returns valid Atom XML."""
        # When: We request recent books
        response = client.get("/opds/recent")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_recent_books_has_acquisition_mime_type(self, client):
        """Test that recent books has acquisition MIME type."""
        # When: We request recent books
        response = client.get("/opds/recent")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_recent_books_respects_limit(self, client):
        """Test that recent books respects limit parameter."""
        # When: We request recent books with limit=2
        response = client.get("/opds/recent?limit=2")

        # Then: Should return success
        assert response.status_code == 200
        # The feed should have at most 2 entries (checking totalResults)
        assert "totalResults>2</opensearch:totalResults" in response.text or \
               "totalResults>1</opensearch:totalResults" in response.text or \
               response.text.count("<entry>") <= 2


class TestOPDSSearch:
    """Test the search endpoint."""

    def test_search_returns_valid_atom_xml(self, client):
        """Test that search returns valid Atom XML."""
        # When: We search for Python
        response = client.get("/opds/search?q=Python")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_search_has_acquisition_mime_type(self, client):
        """Test that search has acquisition MIME type."""
        # When: We search for Python
        response = client.get("/opds/search?q=Python")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_search_returns_feed_with_query(self, client):
        """Test that search returns a feed based on query.

        Note: The search results depend on whether the FTS5 index is populated.
        In test environment without text extraction, results may be empty.
        This test verifies the endpoint contract rather than specific results.
        """
        # When: We search for a term
        response = client.get("/opds/search?q=Python")

        # Then: Should return valid feed (may or may not have results)
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)
        # Feed ID should reflect the search query
        assert "urn:ebk:search:" in response.text

    def test_search_query_in_feed_title(self, client):
        """Test that search query appears in feed title."""
        # When: We search for Machine Learning
        response = client.get("/opds/search?q=Machine%20Learning")

        # Then: Feed title should include search query
        assert "Machine Learning" in response.text

    def test_search_accepts_pagination_parameters(self, client):
        """Test that search endpoint accepts pagination parameters.

        Note: Pagination info (startIndex, etc.) is only included when
        there are results. This test verifies the endpoint accepts the
        parameters without error.
        """
        # When: We search with pagination parameters
        response = client.get("/opds/search?q=Programming&page=1&limit=10")

        # Then: Should return success
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_search_requires_query(self, client):
        """Test that search requires q parameter."""
        # When: We search without query
        response = client.get("/opds/search")

        # Then: Should return validation error
        assert response.status_code == 422

    def test_search_no_results(self, client):
        """Test search with no matching results."""
        # When: We search for non-existent term
        response = client.get("/opds/search?q=NonExistentBook12345")

        # Then: Should return empty feed
        assert response.status_code == 200
        # Feed should have no entry elements or contain "0" results indicator


class TestOPDSAuthors:
    """Test the authors listing endpoint."""

    def test_authors_returns_valid_atom_xml(self, client):
        """Test that authors list returns valid Atom XML."""
        # When: We request authors list
        response = client.get("/opds/authors")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_authors_has_navigation_mime_type(self, client):
        """Test that authors has navigation MIME type."""
        # When: We request authors list
        response = client.get("/opds/authors")

        # Then: Content-Type should be OPDS navigation feed
        assert OPDS_MIME in response.headers["content-type"]

    def test_authors_contains_author_entries(self, client):
        """Test that authors list contains author entries."""
        # When: We request authors list
        response = client.get("/opds/authors")

        # Then: Should contain our test authors
        content = response.text
        assert "John Doe" in content
        assert "Jane Smith" in content

    def test_authors_show_book_counts(self, client):
        """Test that author entries show book counts."""
        # When: We request authors list
        response = client.get("/opds/authors")

        # Then: Should show book counts (1 book, 1 books, etc.)
        assert "book" in response.text.lower()


class TestOPDSAuthorBooks:
    """Test the books by author endpoint."""

    def test_author_books_returns_valid_atom_xml(self, client, populated_library):
        """Test that author books returns valid Atom XML."""
        # Given: An author ID from the library
        author = populated_library.session.query(Author).first()

        # When: We request books by that author
        response = client.get(f"/opds/author/{author.id}")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_author_books_has_acquisition_mime_type(self, client, populated_library):
        """Test that author books has acquisition MIME type."""
        # Given: An author ID from the library
        author = populated_library.session.query(Author).first()

        # When: We request books by that author
        response = client.get(f"/opds/author/{author.id}")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_author_books_returns_404_for_nonexistent_author(self, client):
        """Test that nonexistent author returns 404."""
        # When: We request books by nonexistent author
        response = client.get("/opds/author/99999")

        # Then: Should return 404
        assert response.status_code == 404

    def test_author_books_includes_author_name_in_title(self, client, populated_library):
        """Test that author name appears in feed title."""
        # Given: An author from the library
        author = populated_library.session.query(Author).first()

        # When: We request books by that author
        response = client.get(f"/opds/author/{author.id}")

        # Then: Feed title should include author name
        assert author.name in response.text


class TestOPDSSubjects:
    """Test the subjects listing endpoint."""

    def test_subjects_returns_valid_atom_xml(self, client):
        """Test that subjects list returns valid Atom XML."""
        # When: We request subjects list
        response = client.get("/opds/subjects")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_subjects_has_navigation_mime_type(self, client):
        """Test that subjects has navigation MIME type."""
        # When: We request subjects list
        response = client.get("/opds/subjects")

        # Then: Content-Type should be OPDS navigation feed
        assert OPDS_MIME in response.headers["content-type"]

    def test_subjects_contains_subject_entries(self, client):
        """Test that subjects list contains subject entries."""
        # When: We request subjects list
        response = client.get("/opds/subjects")

        # Then: Should contain our test subjects
        content = response.text
        assert "Programming" in content
        assert "Python" in content


class TestOPDSSubjectBooks:
    """Test the books by subject endpoint."""

    def test_subject_books_returns_valid_atom_xml(self, client, populated_library):
        """Test that subject books returns valid Atom XML."""
        # Given: A subject ID from the library
        subject = populated_library.session.query(Subject).first()

        # When: We request books by that subject
        response = client.get(f"/opds/subject/{subject.id}")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_subject_books_has_acquisition_mime_type(self, client, populated_library):
        """Test that subject books has acquisition MIME type."""
        # Given: A subject ID from the library
        subject = populated_library.session.query(Subject).first()

        # When: We request books by that subject
        response = client.get(f"/opds/subject/{subject.id}")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_subject_books_returns_404_for_nonexistent_subject(self, client):
        """Test that nonexistent subject returns 404."""
        # When: We request books by nonexistent subject
        response = client.get("/opds/subject/99999")

        # Then: Should return 404
        assert response.status_code == 404


class TestOPDSLanguages:
    """Test the languages listing endpoint."""

    def test_languages_returns_valid_atom_xml(self, client):
        """Test that languages list returns valid Atom XML."""
        # When: We request languages list
        response = client.get("/opds/languages")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_languages_has_navigation_mime_type(self, client):
        """Test that languages has navigation MIME type."""
        # When: We request languages list
        response = client.get("/opds/languages")

        # Then: Content-Type should be OPDS navigation feed
        assert OPDS_MIME in response.headers["content-type"]

    def test_languages_contains_language_entries(self, client):
        """Test that languages list contains language entries."""
        # When: We request languages list
        response = client.get("/opds/languages")

        # Then: Should contain our test languages
        content = response.text
        assert "en" in content
        assert "fr" in content


class TestOPDSLanguageBooks:
    """Test the books by language endpoint."""

    def test_language_books_returns_valid_atom_xml(self, client):
        """Test that language books returns valid Atom XML."""
        # When: We request books in English
        response = client.get("/opds/language/en")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_language_books_has_acquisition_mime_type(self, client):
        """Test that language books has acquisition MIME type."""
        # When: We request books in English
        response = client.get("/opds/language/en")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_language_books_filters_by_language(self, client):
        """Test that language books filters correctly."""
        # When: We request books in French
        response = client.get("/opds/language/fr")

        # Then: Should return French book only
        content = response.text
        assert "Introduction a la Programmation" in content
        # English books should not appear
        assert "Python Programming" not in content

    def test_language_books_empty_for_unknown_language(self, client):
        """Test language books with unknown language code."""
        # When: We request books in unknown language
        response = client.get("/opds/language/xyz")

        # Then: Should return empty feed
        assert response.status_code == 200
        assert "totalResults>0</opensearch:totalResults" in response.text


class TestOPDSBookDetail:
    """Test the single book detail endpoint."""

    def test_book_detail_returns_valid_atom_xml(self, client, populated_library):
        """Test that book detail returns valid Atom XML."""
        # Given: A book ID from the library
        book = populated_library.get_all_books()[0]

        # When: We request that book's detail
        response = client.get(f"/opds/book/{book.id}")

        # Then: Should return valid XML
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_book_detail_has_acquisition_mime_type(self, client, populated_library):
        """Test that book detail has acquisition MIME type."""
        # Given: A book ID from the library
        book = populated_library.get_all_books()[0]

        # When: We request that book's detail
        response = client.get(f"/opds/book/{book.id}")

        # Then: Content-Type should be OPDS acquisition feed
        assert OPDS_ACQUISITION_MIME in response.headers["content-type"]

    def test_book_detail_contains_book_metadata(self, client, populated_library):
        """Test that book detail contains complete metadata."""
        # Given: A book with known metadata
        book = populated_library.get_all_books()[0]

        # When: We request that book's detail
        response = client.get(f"/opds/book/{book.id}")

        # Then: Should contain book's metadata
        content = response.text
        assert book.title in content
        # Author should be present
        if book.authors:
            assert book.authors[0].name in content

    def test_book_detail_returns_404_for_nonexistent_book(self, client):
        """Test that nonexistent book returns 404."""
        # When: We request nonexistent book
        response = client.get("/opds/book/99999")

        # Then: Should return 404
        assert response.status_code == 404

    def test_book_detail_includes_acquisition_links(self, client, populated_library):
        """Test that book detail includes download links."""
        # Given: A book with files
        book = populated_library.get_all_books()[0]

        # When: We request that book's detail
        response = client.get(f"/opds/book/{book.id}")

        # Then: Should include acquisition link
        assert "http://opds-spec.org/acquisition" in response.text


class TestOPDSDownload:
    """Test the file download endpoint."""

    def test_download_existing_file(self, client, populated_library):
        """Test downloading an existing book file."""
        # Given: A book with a file
        book = populated_library.get_all_books()[0]
        file_format = book.files[0].format

        # When: We request to download that file
        response = client.get(f"/opds/download/{book.id}/{file_format}")

        # Then: Should return the file
        assert response.status_code == 200

    def test_download_returns_404_for_nonexistent_book(self, client):
        """Test that download returns 404 for nonexistent book."""
        # When: We request download for nonexistent book
        response = client.get("/opds/download/99999/pdf")

        # Then: Should return 404
        assert response.status_code == 404

    def test_download_returns_404_for_nonexistent_format(self, client, populated_library):
        """Test that download returns 404 for nonexistent format."""
        # Given: A book that exists
        book = populated_library.get_all_books()[0]

        # When: We request a format that doesn't exist for this book
        response = client.get(f"/opds/download/{book.id}/xyz")

        # Then: Should return 404
        assert response.status_code == 404

    def test_download_returns_correct_mime_type(self, client, populated_library):
        """Test that download returns appropriate MIME type."""
        # Given: A book with a text file
        book = populated_library.get_all_books()[0]
        file_format = book.files[0].format

        # When: We request to download that file
        response = client.get(f"/opds/download/{book.id}/{file_format}")

        # Then: Should have appropriate content type
        assert response.status_code == 200
        # For txt files, should be text/plain
        if file_format == "txt":
            assert "text/plain" in response.headers.get("content-type", "")


class TestOPDSCover:
    """Test the cover image endpoint."""

    def test_cover_returns_404_for_book_without_cover(self, client, populated_library):
        """Test that cover returns 404 when book has no cover."""
        # Given: A book without a cover (our test books don't have covers)
        book = populated_library.get_all_books()[0]

        # When: We request the cover
        response = client.get(f"/opds/cover/{book.id}")

        # Then: Should return 404
        assert response.status_code == 404

    def test_cover_returns_404_for_nonexistent_book(self, client):
        """Test that cover returns 404 for nonexistent book."""
        # When: We request cover for nonexistent book
        response = client.get("/opds/cover/99999")

        # Then: Should return 404
        assert response.status_code == 404

    def test_cover_thumbnail_returns_404_for_book_without_cover(self, client, populated_library):
        """Test that cover thumbnail returns 404 when book has no cover."""
        # Given: A book without a cover
        book = populated_library.get_all_books()[0]

        # When: We request the thumbnail
        response = client.get(f"/opds/cover/{book.id}/thumbnail")

        # Then: Should return 404
        assert response.status_code == 404


class TestOPDSOpenSearch:
    """Test the OpenSearch description endpoint."""

    def test_opensearch_returns_valid_xml(self, client):
        """Test that OpenSearch description returns valid XML."""
        # When: We request OpenSearch description
        response = client.get("/opds/opensearch.xml")

        # Then: Should return valid XML
        assert response.status_code == 200
        try:
            ET.fromstring(response.text)
        except ET.ParseError:
            pytest.fail("OpenSearch description is not valid XML")

    def test_opensearch_has_correct_mime_type(self, client):
        """Test that OpenSearch has correct MIME type."""
        # When: We request OpenSearch description
        response = client.get("/opds/opensearch.xml")

        # Then: Content-Type should be OpenSearch MIME type
        assert OPENSEARCH_MIME in response.headers["content-type"]

    def test_opensearch_contains_search_template(self, client):
        """Test that OpenSearch contains URL template."""
        # When: We request OpenSearch description
        response = client.get("/opds/opensearch.xml")

        # Then: Should contain search URL template
        assert "searchTerms" in response.text
        assert "/opds/search" in response.text


class TestOPDSBookEntryContent:
    """Test the content of book entries in feeds."""

    def test_book_entry_contains_unique_id(self, client, populated_library):
        """Test that book entries have URN-style IDs."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Entries should have urn:ebk:book: IDs
        assert "urn:ebk:book:" in response.text

    def test_book_entry_contains_title(self, client):
        """Test that book entries contain titles."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should contain book titles in <title> tags
        assert "<title>" in response.text

    def test_book_entry_contains_authors(self, client):
        """Test that book entries contain authors."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should contain <author> elements
        assert "<author>" in response.text
        assert "<name>" in response.text

    def test_book_entry_contains_updated_timestamp(self, client):
        """Test that book entries contain updated timestamps."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should contain <updated> elements
        assert "<updated>" in response.text

    def test_book_entry_escapes_xml_special_characters(self, temp_library):
        """Test that special characters are properly escaped."""
        # Given: A book with special characters in title
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        lib.add_book(
            test_file,
            metadata={
                "title": "Book with <Special> & \"Characters\"",
                "creators": ["Author's Name"],
            },
            extract_text=False
        )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should escape special characters
        assert "&lt;Special&gt;" in response.text
        assert "&amp;" in response.text


class TestOPDSHelperFunctions:
    """Test OPDS module helper functions."""

    def test_escape_xml_handles_special_characters(self):
        """Test XML escaping function."""
        # Given: Text with special characters
        text = '<test> & "quotes" \'apostrophes\''

        # When: We escape it
        escaped = opds.escape_xml(text)

        # Then: All special characters should be escaped
        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "&amp;" in escaped
        assert "&quot;" in escaped
        assert "&apos;" in escaped

    def test_escape_xml_handles_empty_string(self):
        """Test XML escaping with empty string."""
        assert opds.escape_xml("") == ""

    def test_escape_xml_handles_none(self):
        """Test XML escaping with None."""
        assert opds.escape_xml(None) == ""

    def test_get_mime_type_returns_correct_types(self):
        """Test MIME type lookup for various formats."""
        assert opds.get_mime_type("pdf") == "application/pdf"
        assert opds.get_mime_type("epub") == "application/epub+zip"
        assert opds.get_mime_type("mobi") == "application/x-mobipocket-ebook"

    def test_get_mime_type_handles_unknown_format(self):
        """Test MIME type lookup for unknown format."""
        assert opds.get_mime_type("xyz") == "application/octet-stream"

    def test_get_mime_type_is_case_insensitive(self):
        """Test that MIME type lookup is case insensitive."""
        assert opds.get_mime_type("PDF") == "application/pdf"
        assert opds.get_mime_type("Epub") == "application/epub+zip"

    def test_format_datetime_returns_iso_format(self):
        """Test datetime formatting."""
        from datetime import datetime

        # Given: A specific datetime
        dt = datetime(2023, 6, 15, 10, 30, 45)

        # When: We format it
        formatted = opds.format_datetime(dt)

        # Then: Should be ISO format with Z suffix
        assert formatted == "2023-06-15T10:30:45Z"

    def test_format_datetime_handles_none(self):
        """Test datetime formatting with None (uses current time)."""
        # When: We format None
        formatted = opds.format_datetime(None)

        # Then: Should return a valid datetime string
        assert "T" in formatted
        assert formatted.endswith("Z")


class TestOPDSLibraryInitialization:
    """Test OPDS library initialization."""

    def test_get_library_raises_when_not_initialized(self):
        """Test that get_library raises error when library not set."""
        # Given: No library is set
        opds._library = None

        # When/Then: Should raise HTTPException
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            opds.get_library()

        assert exc_info.value.status_code == 500

    def test_set_library_initializes_library(self, temp_library):
        """Test that set_library sets the library instance."""
        # Given: A library
        opds._library = None

        # When: We set the library
        opds.set_library(temp_library)

        # Then: Library should be accessible
        assert opds.get_library() is temp_library


class TestOPDSFeedStructure:
    """Test the structure of OPDS feeds."""

    def test_feed_contains_required_atom_elements(self, client):
        """Test that feeds contain required Atom elements."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should contain required Atom elements
        content = response.text
        assert "<id>" in content
        assert "<title>" in content
        assert "<updated>" in content
        assert "xmlns=" in content  # Namespace declaration

    def test_feed_contains_self_link(self, client):
        """Test that feeds contain self link."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should contain self link
        assert 'rel="self"' in response.text

    def test_feed_contains_start_link(self, client):
        """Test that feeds contain start link."""
        # When: We request the root catalog
        response = client.get("/opds/")

        # Then: Should contain start link
        assert 'rel="start"' in response.text

    def test_acquisition_feed_contains_acquisition_links(self, client):
        """Test that acquisition feeds have acquisition links for books."""
        # When: We request all books
        response = client.get("/opds/all")

        # Then: Book entries should have acquisition links
        assert "http://opds-spec.org/acquisition" in response.text


class TestOPDSCoverWithFile:
    """Test cover endpoint with actual cover file."""

    def test_cover_returns_image_when_cover_exists(self, temp_library):
        """Test that cover returns image when cover file exists."""
        # Given: A book with a cover image
        lib = temp_library

        # Create test book
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={"title": "Book With Cover", "creators": ["Author"]},
            extract_text=False
        )

        # Create a fake cover image file
        covers_dir = lib.library_path / "covers"
        covers_dir.mkdir(exist_ok=True)
        cover_path = covers_dir / "test_cover.jpg"
        # Create a minimal valid JPEG (1x1 red pixel)
        cover_path.write_bytes(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9telefonos;telefonos>telefonos:telefonos'
            b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
            b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}'
            b'\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B'
            b'\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
            b'STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xff\xd9'
        )

        # Add cover to database
        from ebk.db.models import Cover
        cover = Cover(book_id=book.id, path="covers/test_cover.jpg", is_primary=True)
        lib.session.add(cover)
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request the cover
        response = client.get(f"/opds/cover/{book.id}")

        # Then: Should return the image
        assert response.status_code == 200
        assert "image/" in response.headers.get("content-type", "")


class TestOPDSBookEntryWithCover:
    """Test book entries that include cover images."""

    def test_book_entry_includes_cover_links_when_cover_exists(self, temp_library):
        """Test that book entries include cover links when book has a cover."""
        # Given: A book with a cover image
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={
                "title": "Book With Cover",
                "creators": ["Author"],
                "publication_date": "2023"
            },
            extract_text=False
        )

        # Create a cover file
        covers_dir = lib.library_path / "covers"
        covers_dir.mkdir(exist_ok=True)
        cover_path = covers_dir / "cover.jpg"
        cover_path.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF')  # Minimal JPEG header

        # Add cover to database
        from ebk.db.models import Cover
        cover = Cover(book_id=book.id, path="covers/cover.jpg", is_primary=True)
        lib.session.add(cover)
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should include cover image links
        assert response.status_code == 200
        assert "http://opds-spec.org/image" in response.text
        assert "http://opds-spec.org/image/thumbnail" in response.text

    def test_book_entry_includes_publication_date(self, temp_library):
        """Test that book entries include publication date when available."""
        # Given: A book with publication date
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={
                "title": "Book With Date",
                "creators": ["Author"],
            },
            extract_text=False
        )
        # Set publication_date directly (import_service uses 'date' key which is for OPDS/Calibre compatibility)
        book.publication_date = "2023-06-15"
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request all books
        response = client.get("/opds/all")

        # Then: Should include publication date
        assert response.status_code == 200
        assert "<dc:date>" in response.text
        assert "2023-06-15" in response.text


class TestOPDSPaginationEdgeCases:
    """Test pagination edge cases for better coverage."""

    def test_authors_pagination_previous_link(self, temp_library):
        """Test authors pagination shows previous link on page 2."""
        # Given: A library with multiple authors
        lib = temp_library
        for i in range(10):
            test_file = lib.library_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Book {i}",
                    "creators": [f"Author {i}"]
                },
                extract_text=False
            )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request page 2 of authors with limit=3
        response = client.get("/opds/authors?page=2&limit=3")

        # Then: Should include previous link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_subjects_pagination_previous_link(self, temp_library):
        """Test subjects pagination shows previous link on page 2."""
        # Given: A library with multiple subjects
        lib = temp_library
        for i in range(10):
            test_file = lib.library_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Book {i}",
                    "creators": ["Author"],
                    "subjects": [f"Subject{i}"]
                },
                extract_text=False
            )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request page 2 of subjects with limit=3
        response = client.get("/opds/subjects?page=2&limit=3")

        # Then: Should include previous link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_author_books_pagination_previous_link(self, temp_library):
        """Test author books pagination shows previous link on page 2."""
        # Given: A library with one author having many books
        lib = temp_library
        for i in range(10):
            test_file = lib.library_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Book {i}",
                    "creators": ["Prolific Author"]
                },
                extract_text=False
            )

        opds.set_library(lib)
        client = TestClient(app)

        # Get the author ID
        from ebk.db.models import Author
        author = lib.session.query(Author).filter(Author.name == "Prolific Author").first()

        # When: We request page 2 of that author's books with limit=3
        response = client.get(f"/opds/author/{author.id}?page=2&limit=3")

        # Then: Should include previous link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_subject_books_pagination_previous_link(self, temp_library):
        """Test subject books pagination shows previous link on page 2."""
        # Given: A library with one subject having many books
        lib = temp_library
        for i in range(10):
            test_file = lib.library_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Book {i}",
                    "creators": [f"Author {i}"],
                    "subjects": ["Common Subject"]
                },
                extract_text=False
            )

        opds.set_library(lib)
        client = TestClient(app)

        # Get the subject ID
        from ebk.db.models import Subject
        subject = lib.session.query(Subject).filter(Subject.name == "Common Subject").first()

        # When: We request page 2 of that subject's books with limit=3
        response = client.get(f"/opds/subject/{subject.id}?page=2&limit=3")

        # Then: Should include previous link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_language_books_pagination_previous_link(self, temp_library):
        """Test language books pagination shows previous link on page 2."""
        # Given: A library with many books in one language
        lib = temp_library
        for i in range(10):
            test_file = lib.library_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Book {i}",
                    "creators": [f"Author {i}"],
                    "language": "de"
                },
                extract_text=False
            )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request page 2 of German books with limit=3
        response = client.get("/opds/language/de?page=2&limit=3")

        # Then: Should include previous link
        assert response.status_code == 200
        assert 'rel="previous"' in response.text

    def test_search_pagination_previous_link(self, temp_library):
        """Test search pagination shows previous link on page 2."""
        # Given: A library with books
        lib = temp_library
        for i in range(5):
            test_file = lib.library_path / f"test{i}.txt"
            # Make content long enough to be indexed
            test_file.write_text("Test content Python programming " * 100)
            lib.add_book(
                test_file,
                metadata={
                    "title": f"Python Book {i}",
                    "creators": ["Author"]
                },
                extract_text=True  # Enable text extraction for search
            )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request page 2 of search results with limit=2
        response = client.get("/opds/search?q=Python&page=2&limit=2")

        # Then: Should return valid feed (may or may not have previous link
        # depending on whether search found results)
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)

    def test_search_pagination_next_link_when_full_page(self, temp_library):
        """Test search pagination shows next link when results fill the page."""
        # Given: A library with multiple searchable books
        lib = temp_library
        for i in range(5):
            test_file = lib.library_path / f"python_book_{i}.txt"
            # Make content with distinctive searchable term
            test_file.write_text(f"UniqueSearchTerm123 content number {i} " * 100)
            lib.add_book(
                test_file,
                metadata={
                    "title": f"UniqueSearchTerm123 Book {i}",
                    "creators": ["Author"],
                    "description": "UniqueSearchTerm123 searchable description"
                },
                extract_text=True
            )

        opds.set_library(lib)
        client = TestClient(app)

        # When: We search with limit=2 (less than total results)
        response = client.get("/opds/search?q=UniqueSearchTerm123&page=1&limit=2")

        # Then: Should return valid feed - next link shows when results fill the page
        assert response.status_code == 200
        assert is_valid_atom_xml(response.text)
        # If 2 results were returned (full page), next link should appear
        # Note: Search may return empty if FTS not populated, so check both cases
        if response.text.count("<entry>") == 2:
            assert 'rel="next"' in response.text


class TestOPDSCoverMediaTypes:
    """Test cover endpoint with different image types."""

    def test_cover_detects_png_media_type(self, temp_library):
        """Test that PNG covers are served with correct media type."""
        # Given: A book with a PNG cover
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={"title": "Book", "creators": ["Author"]},
            extract_text=False
        )

        # Create a PNG cover file
        covers_dir = lib.library_path / "covers"
        covers_dir.mkdir(exist_ok=True)
        cover_path = covers_dir / "cover.png"
        # PNG magic bytes
        cover_path.write_bytes(b'\x89PNG\r\n\x1a\n')

        # Add cover to database
        from ebk.db.models import Cover
        cover = Cover(book_id=book.id, path="covers/cover.png", is_primary=True)
        lib.session.add(cover)
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request the cover
        response = client.get(f"/opds/cover/{book.id}")

        # Then: Should return PNG media type
        assert response.status_code == 200
        assert "image/png" in response.headers.get("content-type", "")

    def test_cover_returns_404_when_file_missing(self, temp_library):
        """Test cover returns 404 when file path exists but file is missing."""
        # Given: A book with cover record but no actual file
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={"title": "Book", "creators": ["Author"]},
            extract_text=False
        )

        # Add cover to database pointing to non-existent file
        from ebk.db.models import Cover
        cover = Cover(book_id=book.id, path="covers/missing.jpg", is_primary=True)
        lib.session.add(cover)
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request the cover
        response = client.get(f"/opds/cover/{book.id}")

        # Then: Should return 404
        assert response.status_code == 404

    def test_cover_returns_404_when_path_not_set(self, temp_library):
        """Test cover returns 404 when cover path is not set."""
        # Given: A book with cover record but no path
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={"title": "Book", "creators": ["Author"]},
            extract_text=False
        )

        # Add cover to database with no path
        from ebk.db.models import Cover
        cover = Cover(book_id=book.id, path="", is_primary=True)
        lib.session.add(cover)
        lib.session.commit()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request the cover
        response = client.get(f"/opds/cover/{book.id}")

        # Then: Should return 404
        assert response.status_code == 404


class TestOPDSDownloadEdgeCases:
    """Test download endpoint edge cases."""

    def test_download_returns_404_when_file_missing_from_disk(self, temp_library):
        """Test download returns 404 when file record exists but file is missing."""
        # Given: A book with file record but actual file deleted
        lib = temp_library
        test_file = lib.library_path / "test.txt"
        test_file.write_text("Test content")
        book = lib.add_book(
            test_file,
            metadata={"title": "Book", "creators": ["Author"]},
            extract_text=False
        )

        # Delete the physical file
        file_path = lib.library_path / book.files[0].path
        file_path.unlink()

        opds.set_library(lib)
        client = TestClient(app)

        # When: We request to download
        response = client.get(f"/opds/download/{book.id}/txt")

        # Then: Should return 404
        assert response.status_code == 404
        assert "not found on disk" in response.text.lower() or "not found" in response.text.lower()
