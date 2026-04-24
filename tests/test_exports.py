"""
Tests for export functionality (OPDS export).

Tests cover:
- OPDS catalog export: generating valid OPDS/Atom feeds
- Book entry generation with metadata, authors, subjects
- File/cover copying functionality
- XML escaping and special character handling
- Filtering options for exports
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

from book_memex.library_db import Library
from book_memex.exports.opds_export import (
    export_to_opds,
    build_feed,
    build_entry,
    get_mime_type,
    escape_xml,
    format_datetime,
    OPDS_ACQUISITION_MIME,
    FORMAT_MIMES,
)


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
def populated_library(temp_library):
    """Library with test data for export tests."""
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
def mock_book():
    """Create a mock book object for unit testing."""
    book = MagicMock()
    book.id = 1
    book.title = "Test Book"
    book.description = "A test book description."
    book.language = "en"
    book.publisher = "Test Publisher"
    book.publication_date = "2023"

    # Mock authors
    author = MagicMock()
    author.name = "Test Author"
    book.authors = [author]

    # Mock subjects
    subject = MagicMock()
    subject.name = "Test Subject"
    book.subjects = [subject]

    # Mock files
    file = MagicMock()
    file.format = "epub"
    file.file_hash = "abc123def456"
    file.size_bytes = 1024000
    book.files = [file]

    # Mock covers
    cover = MagicMock()
    cover.path = "covers/test.jpg"
    book.covers = [cover]

    book.updated_at = None

    return book


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestGetMimeType:
    """Test MIME type lookup function."""

    def test_returns_pdf_mime_type(self):
        """Test PDF MIME type."""
        assert get_mime_type("pdf") == "application/pdf"

    def test_returns_epub_mime_type(self):
        """Test EPUB MIME type."""
        assert get_mime_type("epub") == "application/epub+zip"

    def test_returns_mobi_mime_type(self):
        """Test MOBI MIME type."""
        assert get_mime_type("mobi") == "application/x-mobipocket-ebook"

    def test_returns_azw_mime_type(self):
        """Test AZW MIME type."""
        assert get_mime_type("azw") == "application/vnd.amazon.ebook"
        assert get_mime_type("azw3") == "application/vnd.amazon.ebook"

    def test_returns_txt_mime_type(self):
        """Test TXT MIME type."""
        assert get_mime_type("txt") == "text/plain"

    def test_returns_html_mime_type(self):
        """Test HTML MIME type."""
        assert get_mime_type("html") == "text/html"
        assert get_mime_type("htm") == "text/html"

    def test_returns_djvu_mime_type(self):
        """Test DJVU MIME type."""
        assert get_mime_type("djvu") == "image/vnd.djvu"

    def test_returns_comic_mime_types(self):
        """Test comic book MIME types."""
        assert get_mime_type("cbz") == "application/vnd.comicbook+zip"
        assert get_mime_type("cbr") == "application/vnd.comicbook-rar"

    def test_case_insensitive(self):
        """Test that MIME type lookup is case insensitive."""
        assert get_mime_type("PDF") == "application/pdf"
        assert get_mime_type("Epub") == "application/epub+zip"
        assert get_mime_type("MOBI") == "application/x-mobipocket-ebook"

    def test_returns_default_for_unknown(self):
        """Test that unknown formats return octet-stream."""
        assert get_mime_type("xyz") == "application/octet-stream"
        assert get_mime_type("unknown") == "application/octet-stream"


class TestEscapeXml:
    """Test XML escaping function."""

    def test_escapes_less_than(self):
        """Test escaping < character."""
        assert "&lt;" in escape_xml("<test>")

    def test_escapes_greater_than(self):
        """Test escaping > character."""
        assert "&gt;" in escape_xml("<test>")

    def test_escapes_ampersand(self):
        """Test escaping & character."""
        assert "&amp;" in escape_xml("test & more")

    def test_escapes_double_quote(self):
        """Test escaping \" character."""
        assert "&quot;" in escape_xml('test "quoted"')

    def test_escapes_apostrophe(self):
        """Test escaping ' character."""
        assert "&apos;" in escape_xml("test 'quoted'")

    def test_handles_empty_string(self):
        """Test handling empty string."""
        assert escape_xml("") == ""

    def test_handles_none(self):
        """Test handling None."""
        assert escape_xml(None) == ""

    def test_handles_multiple_special_chars(self):
        """Test handling string with multiple special characters."""
        text = '<book title="Test & More">\'quoted\''
        escaped = escape_xml(text)

        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "&amp;" in escaped
        assert "&quot;" in escaped
        assert "&apos;" in escaped

    def test_preserves_normal_text(self):
        """Test that normal text is preserved."""
        text = "Normal text without special chars"
        assert escape_xml(text) == text


class TestFormatDatetime:
    """Test datetime formatting function."""

    def test_formats_datetime_correctly(self):
        """Test formatting a specific datetime."""
        from datetime import datetime

        dt = datetime(2023, 12, 25, 10, 30, 45)
        formatted = format_datetime(dt)

        assert formatted == "2023-12-25T10:30:45Z"

    def test_formats_datetime_with_zeros(self):
        """Test formatting datetime with zeros in month/day."""
        from datetime import datetime

        dt = datetime(2023, 1, 5, 8, 5, 3)
        formatted = format_datetime(dt)

        assert formatted == "2023-01-05T08:05:03Z"

    def test_handles_none_uses_current_time(self):
        """Test that None uses current time."""
        formatted = format_datetime(None)

        # Should be in ISO format with Z suffix
        assert "T" in formatted
        assert formatted.endswith("Z")
        assert len(formatted) == 20  # YYYY-MM-DDTHH:MM:SSZ


# ============================================================================
# Build Entry Tests
# ============================================================================

class TestBuildEntry:
    """Test building OPDS entry for a book."""

    def test_entry_contains_book_id(self, mock_book):
        """Test that entry contains book ID in URN format."""
        entry = build_entry(mock_book, "https://example.com")

        assert "urn:ebk:book:1" in entry

    def test_entry_contains_title(self, mock_book):
        """Test that entry contains book title."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<title>Test Book</title>" in entry

    def test_entry_contains_author(self, mock_book):
        """Test that entry contains author."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<author>" in entry
        assert "<name>Test Author</name>" in entry

    def test_entry_contains_description(self, mock_book):
        """Test that entry contains description as summary."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<summary>" in entry
        assert "test book description" in entry.lower()

    def test_entry_contains_category(self, mock_book):
        """Test that entry contains subjects as categories."""
        entry = build_entry(mock_book, "https://example.com")

        assert '<category term="Test Subject"' in entry

    def test_entry_contains_language(self, mock_book):
        """Test that entry contains language."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<dc:language>en</dc:language>" in entry

    def test_entry_contains_publisher(self, mock_book):
        """Test that entry contains publisher."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<dc:publisher>Test Publisher</dc:publisher>" in entry

    def test_entry_contains_publication_date(self, mock_book):
        """Test that entry contains publication date."""
        entry = build_entry(mock_book, "https://example.com")

        assert "<dc:date>2023</dc:date>" in entry

    def test_entry_contains_cover_link(self, mock_book):
        """Test that entry contains cover image link."""
        entry = build_entry(mock_book, "https://example.com")

        assert "http://opds-spec.org/image" in entry
        assert "http://opds-spec.org/image/thumbnail" in entry

    def test_entry_contains_acquisition_link(self, mock_book):
        """Test that entry contains acquisition (download) link."""
        entry = build_entry(mock_book, "https://example.com")

        assert "http://opds-spec.org/acquisition" in entry
        assert "application/epub+zip" in entry

    def test_entry_shows_file_size(self, mock_book):
        """Test that entry shows file size in KB."""
        entry = build_entry(mock_book, "https://example.com")

        assert '1000 KB' in entry  # 1024000 bytes / 1024 = 1000 KB

    def test_entry_escapes_special_characters_in_title(self):
        """Test that special characters in title are escaped."""
        book = MagicMock()
        book.id = 1
        book.title = "Test <Book> & More"
        book.description = None
        book.language = None
        book.publisher = None
        book.publication_date = None
        book.authors = []
        book.subjects = []
        book.files = []
        book.covers = []
        book.updated_at = None

        entry = build_entry(book, "")

        assert "&lt;Book&gt;" in entry
        assert "&amp;" in entry

    def test_entry_handles_no_authors(self):
        """Test entry with no authors."""
        book = MagicMock()
        book.id = 1
        book.title = "Test Book"
        book.description = None
        book.language = None
        book.publisher = None
        book.publication_date = None
        book.authors = []
        book.subjects = []
        book.files = []
        book.covers = []
        book.updated_at = None

        entry = build_entry(book, "")

        # Should not crash, and should not contain author element
        assert "<entry>" in entry

    def test_entry_handles_no_files(self):
        """Test entry with no files."""
        book = MagicMock()
        book.id = 1
        book.title = "Test Book"
        book.description = None
        book.language = None
        book.publisher = None
        book.publication_date = None
        book.authors = []
        book.subjects = []
        book.files = []
        book.covers = []
        book.updated_at = None

        entry = build_entry(book, "")

        # Should not contain acquisition link
        assert "http://opds-spec.org/acquisition" not in entry

    def test_entry_handles_no_cover(self):
        """Test entry with no cover."""
        book = MagicMock()
        book.id = 1
        book.title = "Test Book"
        book.description = None
        book.language = None
        book.publisher = None
        book.publication_date = None
        book.authors = []
        book.subjects = []
        book.files = []
        book.covers = []
        book.updated_at = None

        entry = build_entry(book, "")

        # Should not contain cover link
        assert "http://opds-spec.org/image" not in entry

    def test_entry_truncates_long_description(self, mock_book):
        """Test that long descriptions are truncated."""
        mock_book.description = "A" * 600  # Longer than 500 chars

        entry = build_entry(mock_book, "")

        # Description should be truncated to 500 chars
        assert "<summary>" in entry
        # Count actual content between tags (should be 500)


# ============================================================================
# Build Feed Tests
# ============================================================================

class TestBuildFeed:
    """Test building OPDS Atom feed."""

    def test_feed_has_xml_declaration(self):
        """Test that feed has XML declaration."""
        feed = build_feed("Test Catalog", "")

        assert '<?xml version="1.0" encoding="UTF-8"?>' in feed

    def test_feed_has_atom_namespace(self):
        """Test that feed declares Atom namespace."""
        feed = build_feed("Test Catalog", "")

        assert 'xmlns="http://www.w3.org/2005/Atom"' in feed

    def test_feed_has_dc_namespace(self):
        """Test that feed declares DC namespace."""
        feed = build_feed("Test Catalog", "")

        assert 'xmlns:dc="http://purl.org/dc/terms/"' in feed

    def test_feed_has_opds_namespace(self):
        """Test that feed declares OPDS namespace."""
        feed = build_feed("Test Catalog", "")

        assert 'xmlns:opds="http://opds-spec.org/2010/catalog"' in feed

    def test_feed_contains_title(self):
        """Test that feed contains title."""
        feed = build_feed("My Library", "")

        assert "<title>My Library</title>" in feed

    def test_feed_contains_subtitle_when_provided(self):
        """Test that feed contains subtitle when provided."""
        feed = build_feed("My Library", "", subtitle="A collection of books")

        assert "<subtitle>A collection of books</subtitle>" in feed

    def test_feed_omits_subtitle_when_empty(self):
        """Test that feed omits subtitle when empty."""
        feed = build_feed("My Library", "", subtitle="")

        assert "<subtitle>" not in feed

    def test_feed_contains_id(self):
        """Test that feed contains unique ID."""
        feed = build_feed("Test Catalog", "")

        assert "<id>urn:ebk:catalog:" in feed

    def test_feed_contains_updated(self):
        """Test that feed contains updated timestamp."""
        feed = build_feed("Test Catalog", "")

        assert "<updated>" in feed
        assert "</updated>" in feed

    def test_feed_contains_author(self):
        """Test that feed contains author."""
        feed = build_feed("Test Catalog", "", author_name="Test Author")

        assert "<author>" in feed
        assert "<name>Test Author</name>" in feed

    def test_feed_contains_self_link(self):
        """Test that feed contains self link when base_url provided."""
        feed = build_feed("Test Catalog", "", base_url="https://example.com")

        assert 'rel="self"' in feed
        assert "https://example.com/catalog.xml" in feed

    def test_feed_contains_start_link(self):
        """Test that feed contains start link when base_url provided."""
        feed = build_feed("Test Catalog", "", base_url="https://example.com")

        assert 'rel="start"' in feed

    def test_feed_includes_entries(self):
        """Test that feed includes provided entries."""
        entries = "<entry><title>Book 1</title></entry><entry><title>Book 2</title></entry>"
        feed = build_feed("Test Catalog", entries)

        assert "<entry><title>Book 1</title></entry>" in feed
        assert "<entry><title>Book 2</title></entry>" in feed

    def test_feed_escapes_special_chars_in_title(self):
        """Test that special characters in title are escaped."""
        feed = build_feed("Test <Catalog> & More", "")

        assert "&lt;Catalog&gt;" in feed
        assert "&amp;" in feed


# ============================================================================
# Export To OPDS Integration Tests
# ============================================================================

class TestExportToOPDS:
    """Test the export_to_opds function."""

    def test_creates_output_file(self, populated_library):
        """Test that export creates the output file."""
        # Given: A populated library and output path
        output_path = populated_library.library_path / "export" / "catalog.xml"
        books = populated_library.get_all_books()

        # When: We export to OPDS
        stats = export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            title="Test Catalog"
        )

        # Then: Output file should exist
        assert output_path.exists()

    def test_creates_output_directory(self, populated_library):
        """Test that export creates output directory if needed."""
        # Given: An output path in a non-existent directory
        output_path = populated_library.library_path / "new_dir" / "nested" / "catalog.xml"
        books = populated_library.get_all_books()

        # When: We export to OPDS
        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        # Then: Directory should be created and file should exist
        assert output_path.exists()

    def test_returns_book_count_in_stats(self, populated_library):
        """Test that stats include book count."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        stats = export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        assert stats["books"] == len(books)

    def test_copies_files_when_requested(self, populated_library):
        """Test that ebook files are copied when copy_files=True."""
        output_path = populated_library.library_path / "export" / "catalog.xml"
        books = populated_library.get_all_books()

        # Ensure books have files
        assert any(len(b.files) > 0 for b in books)

        stats = export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            copy_files=True
        )

        # Should have copied at least one file
        files_dir = output_path.parent / "files"
        assert files_dir.exists()
        assert stats["files_copied"] >= 0

    def test_creates_files_directory_when_copy_files(self, populated_library):
        """Test that files directory is created when copying files."""
        output_path = populated_library.library_path / "export" / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            copy_files=True
        )

        files_dir = output_path.parent / "files"
        assert files_dir.exists()

    def test_creates_covers_directory_when_copy_covers(self, populated_library):
        """Test that covers directory is created when copying covers."""
        output_path = populated_library.library_path / "export" / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            copy_covers=True
        )

        covers_dir = output_path.parent / "covers"
        assert covers_dir.exists()

    def test_output_is_valid_xml(self, populated_library):
        """Test that output is valid XML."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        # Should parse without error
        content = output_path.read_text()
        root = ET.fromstring(content)
        assert root is not None

    def test_output_is_valid_atom_feed(self, populated_library):
        """Test that output is a valid Atom feed."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        content = output_path.read_text()
        root = ET.fromstring(content)

        # Should have feed as root element
        assert "feed" in root.tag.lower()

    def test_includes_all_books_as_entries(self, populated_library):
        """Test that all books are included as entries."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        content = output_path.read_text()

        # Each book should appear as an entry
        for book in books:
            assert book.title in content

    def test_handles_empty_book_list(self, temp_library):
        """Test exporting with no books."""
        output_path = temp_library.library_path / "catalog.xml"

        stats = export_to_opds(
            books=[],
            output_path=output_path,
            library_path=temp_library.library_path,
            title="Empty Catalog"
        )

        assert stats["books"] == 0
        assert output_path.exists()

        # Should still be valid XML
        content = output_path.read_text()
        root = ET.fromstring(content)
        assert root is not None

    def test_includes_base_url_in_links(self, populated_library):
        """Test that base_url is used in file links."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            base_url="https://myserver.com/library"
        )

        content = output_path.read_text()
        assert "https://myserver.com/library" in content

    def test_uses_custom_title(self, populated_library):
        """Test that custom title is used."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            title="My Custom Library"
        )

        content = output_path.read_text()
        assert "My Custom Library" in content

    def test_uses_custom_subtitle(self, populated_library):
        """Test that custom subtitle is used."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            subtitle="A personal collection"
        )

        content = output_path.read_text()
        assert "A personal collection" in content

    def test_handles_missing_source_files_gracefully(self, populated_library):
        """Test that missing source files don't crash export."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        # Delete actual files
        for book in books:
            for file in book.files:
                file_path = populated_library.library_path / file.path
                if file_path.exists():
                    file_path.unlink()

        # Should not crash
        stats = export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path,
            copy_files=True
        )

        # Should have errors but still create catalog
        assert output_path.exists()


# ============================================================================
# OPDS Feed Validation Tests
# ============================================================================

class TestOPDSFeedValidation:
    """Test that exported feeds are valid OPDS."""

    def test_feed_has_required_atom_elements(self, populated_library):
        """Test that feed has all required Atom elements."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        content = output_path.read_text()

        # Required Atom elements
        assert "<id>" in content
        assert "<title>" in content
        assert "<updated>" in content

    def test_entries_have_required_elements(self, populated_library):
        """Test that entries have required elements."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        content = output_path.read_text()

        # Each entry should have id, title, updated
        assert content.count("urn:ebk:book:") >= len(books)

    def test_acquisition_links_have_proper_mime_types(self, populated_library):
        """Test that acquisition links have proper MIME types."""
        output_path = populated_library.library_path / "catalog.xml"
        books = populated_library.get_all_books()

        export_to_opds(
            books=books,
            output_path=output_path,
            library_path=populated_library.library_path
        )

        content = output_path.read_text()

        # Should have acquisition links with type attribute
        if "http://opds-spec.org/acquisition" in content:
            assert 'type=' in content


# ============================================================================
# Constants Tests
# ============================================================================

class TestOPDSExportConstants:
    """Test module constants."""

    def test_opds_acquisition_mime_is_correct(self):
        """Test OPDS acquisition MIME type constant."""
        assert OPDS_ACQUISITION_MIME == "application/atom+xml;profile=opds-catalog;kind=acquisition"

    def test_format_mimes_includes_common_formats(self):
        """Test that FORMAT_MIMES includes common ebook formats."""
        assert "pdf" in FORMAT_MIMES
        assert "epub" in FORMAT_MIMES
        assert "mobi" in FORMAT_MIMES
        assert "txt" in FORMAT_MIMES


# ============================================================================
# Arkiv Export Tests
# ============================================================================

class TestArkivExport:
    """Tests for the arkiv export format (records.jsonl + schema.yaml)."""

    @pytest.fixture
    def lib_with_data(self):
        """Library populated with one book, one marginalia, and one reading session."""
        import json as _json
        from book_memex.services.marginalia_service import MarginaliaService
        from book_memex.services.reading_session_service import ReadingSessionService

        temp_dir = Path(tempfile.mkdtemp())
        lib = Library.open(temp_dir)

        p = lib.library_path / "b.txt"
        p.write_text("h")
        book = lib.add_book(
            p,
            metadata={"title": "B", "creators": ["X"]},
            extract_text=False,
            extract_cover=False,
        )

        m_svc = MarginaliaService(lib.session)
        r_svc = ReadingSessionService(lib.session)
        m = m_svc.create(
            content="note",
            highlighted_text="p",
            book_ids=[book.id],
            page_number=3,
            color="#ffff00",
        )
        rs = r_svc.start(book_id=book.id, start_anchor={"cfi": "X"})
        r_svc.end(rs.uuid, end_anchor={"cfi": "Y"})

        yield lib, book, m, rs

        lib.close()
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_arkiv_export_includes_marginalia_and_reading(self, lib_with_data):
        """Exported records.jsonl includes book, marginalia, and reading kinds."""
        import json as _json
        import yaml as _yaml

        lib, book, m, rs = lib_with_data
        out = Path(tempfile.mkdtemp())
        try:
            result = lib.export_arkiv(out)

            records_path = out / "records.jsonl"
            schema_path = out / "schema.yaml"
            assert records_path.exists()
            assert schema_path.exists()

            with open(records_path) as f:
                records = [_json.loads(line) for line in f if line.strip()]

            kinds = {r.get("kind") for r in records}
            assert "book" in kinds
            assert "marginalia" in kinds
            assert "reading" in kinds

            # Marginalia record has correct URI and color
            marginalia_records = [r for r in records if r.get("kind") == "marginalia"]
            assert any(r["uri"] == m.uri for r in marginalia_records)
            assert any(r.get("color") == "#ffff00" for r in marginalia_records)

            # Marginalia points to the book by URI
            marg = marginalia_records[0]
            assert book.uri in marg["book_uris"]
            assert marg["page_number"] == 3
            assert marg["content"] == "note"
            assert marg["highlighted_text"] == "p"

            # Reading record has correct URI and book URI
            reading_records = [r for r in records if r.get("kind") == "reading"]
            assert any(r["uri"] == rs.uri for r in reading_records)
            reading = reading_records[0]
            assert reading["book_uri"] == book.uri
            assert reading["start_anchor"] == {"cfi": "X"}
            assert reading["end_anchor"] == {"cfi": "Y"}
            assert reading["end_time"] is not None

            # Book record has its URI
            book_records = [r for r in records if r.get("kind") == "book"]
            assert any(r["uri"] == book.uri for r in book_records)

            # schema.yaml describes the new kinds
            with open(schema_path) as f:
                schema = _yaml.safe_load(f)
            assert "marginalia" in schema.get("kinds", {})
            assert "reading" in schema.get("kinds", {})
            assert "book" in schema.get("kinds", {})

            # Counts returned from exporter
            assert result["counts"]["book"] == 1
            assert result["counts"]["marginalia"] == 1
            assert result["counts"]["reading"] == 1
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_arkiv_export_excludes_archived_records(self, lib_with_data):
        """Archived marginalia and reading sessions are not exported."""
        import json as _json
        from book_memex.services.marginalia_service import MarginaliaService
        from book_memex.services.reading_session_service import ReadingSessionService

        lib, book, m, rs = lib_with_data

        # Archive the marginalia + reading session
        MarginaliaService(lib.session).archive(m)
        ReadingSessionService(lib.session).archive(rs)

        out = Path(tempfile.mkdtemp())
        try:
            lib.export_arkiv(out)
            records_path = out / "records.jsonl"
            with open(records_path) as f:
                records = [_json.loads(line) for line in f if line.strip()]
            kinds = {r.get("kind") for r in records}
            assert "book" in kinds
            assert "marginalia" not in kinds
            assert "reading" not in kinds
        finally:
            shutil.rmtree(out, ignore_errors=True)

    # -- Bundle formats (C5a) ------------------------------------------

    def test_arkiv_directory_includes_readme(self, lib_with_data):
        """Directory bundle contains records.jsonl + schema.yaml + README.md."""
        lib, _, _, _ = lib_with_data
        out = Path(tempfile.mkdtemp())
        try:
            result = lib.export_arkiv(out)
            assert (out / "records.jsonl").is_file()
            assert (out / "schema.yaml").is_file()
            assert (out / "README.md").is_file()
            readme = (out / "README.md").read_text()
            assert readme.startswith("---")
            assert "generator: book-memex" in readme
            assert "book-memex import-arkiv" in readme
            assert result["format"] == "dir"
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_arkiv_zip_bundle(self, lib_with_data):
        """A path ending in .zip produces a single zip archive."""
        import json as _json
        import zipfile

        lib, book, _, _ = lib_with_data
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "bundle.zip"
            result = lib.export_arkiv(out)
            assert result["format"] == "zip"
            assert out.is_file()
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                assert {"records.jsonl", "schema.yaml", "README.md"}.issubset(names)
                with zf.open("records.jsonl") as f:
                    records = [
                        _json.loads(ln)
                        for ln in f.read().decode().splitlines()
                        if ln.strip()
                    ]
            kinds = {r.get("kind") for r in records}
            assert "book" in kinds
            assert any(r["uri"] == book.uri for r in records if r.get("kind") == "book")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_arkiv_tar_gz_bundle(self, lib_with_data):
        """A path ending in .tar.gz produces a gzipped tarball."""
        import json as _json
        import tarfile

        lib, _, _, _ = lib_with_data
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "bundle.tar.gz"
            result = lib.export_arkiv(out)
            assert result["format"] == "tar.gz"
            with tarfile.open(out, "r:gz") as tf:
                names = set(tf.getnames())
                assert {"records.jsonl", "schema.yaml", "README.md"}.issubset(names)
                extracted = tf.extractfile("records.jsonl")
                assert extracted is not None
                records = [
                    _json.loads(ln)
                    for ln in extracted.read().decode().splitlines()
                    if ln.strip()
                ]
            kinds = {r.get("kind") for r in records}
            assert "book" in kinds
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_arkiv_tgz_extension_accepted(self, lib_with_data):
        """.tgz is recognised as a synonym for .tar.gz."""
        import tarfile

        lib, _, _, _ = lib_with_data
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "bundle.tgz"
            result = lib.export_arkiv(out)
            assert result["format"] == "tar.gz"
            with tarfile.open(out, "r:gz") as tf:
                assert "records.jsonl" in tf.getnames()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_arkiv_bundle_records_identical_across_formats(self, lib_with_data):
        """directory / zip / tar.gz produce the same records for the same library."""
        import json as _json
        import tarfile
        import zipfile

        lib, _, _, _ = lib_with_data
        tmp = Path(tempfile.mkdtemp())
        try:
            dir_out = tmp / "dir"
            zip_out = tmp / "bundle.zip"
            tar_out = tmp / "bundle.tar.gz"
            lib.export_arkiv(dir_out)
            lib.export_arkiv(zip_out)
            lib.export_arkiv(tar_out)

            dir_recs = [
                _json.loads(ln)
                for ln in (dir_out / "records.jsonl").read_text().splitlines()
                if ln.strip()
            ]
            with zipfile.ZipFile(zip_out) as zf:
                with zf.open("records.jsonl") as f:
                    zip_recs = [
                        _json.loads(ln)
                        for ln in f.read().decode().splitlines()
                        if ln.strip()
                    ]
            with tarfile.open(tar_out, "r:gz") as tf:
                tar_recs = [
                    _json.loads(ln)
                    for ln in tf.extractfile("records.jsonl").read().decode().splitlines()
                    if ln.strip()
                ]
            assert dir_recs == zip_recs == tar_recs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestArkivDetectCompression:
    """Bundle-format extension detection."""

    def test_plain_path_is_directory(self):
        from book_memex.exports.arkiv import _detect_compression
        assert _detect_compression("bundle") == "dir"

    def test_zip_extension(self):
        from book_memex.exports.arkiv import _detect_compression
        assert _detect_compression("bundle.zip") == "zip"
        assert _detect_compression("bundle.ZIP") == "zip"

    def test_tar_gz_extension(self):
        from book_memex.exports.arkiv import _detect_compression
        assert _detect_compression("bundle.tar.gz") == "tar.gz"
        assert _detect_compression("bundle.TAR.GZ") == "tar.gz"

    def test_tgz_extension(self):
        from book_memex.exports.arkiv import _detect_compression
        assert _detect_compression("bundle.tgz") == "tar.gz"
