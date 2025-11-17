"""
Tests for ebk service modules (import and text extraction).
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import hashlib

from ebooklib import epub
import ebooklib

from ebk.library_db import Library
from ebk.services.import_service import ImportService
from ebk.services.text_extraction import TextExtractionService
from ebk.db.models import Book, File, ExtractedText


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    # Cleanup
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestImportService:
    """Test import service functionality."""

    def test_import_service_creation(self, temp_library):
        """Test creating an import service."""
        service = ImportService(temp_library.library_path, temp_library.session)
        assert service is not None
        assert (temp_library.library_path / 'files').exists()
        assert (temp_library.library_path / 'covers').exists()

    def test_compute_file_hash_enables_deduplication(self, temp_library):
        """Test that file hashing enables duplicate file detection."""
        # Given: Two files with identical content
        test_file1 = temp_library.library_path / "test1.txt"
        test_file1.write_text("Test content for hashing")

        test_file2 = temp_library.library_path / "test2.txt"
        test_file2.write_text("Test content for hashing")

        # When: We compute their hashes
        file_hash1 = ImportService._compute_file_hash(test_file1)
        file_hash2 = ImportService._compute_file_hash(test_file2)

        # Then: Identical files should produce identical hashes (for deduplication)
        assert file_hash1 == file_hash2

        # And: Different content should produce different hashes
        test_file3 = temp_library.library_path / "test3.txt"
        test_file3.write_text("Different content")
        file_hash3 = ImportService._compute_file_hash(test_file3)
        assert file_hash3 != file_hash1

    def test_generate_unique_id_with_isbn(self):
        """Test that unique ID generation uses ISBN when available."""
        # Given: Metadata with an ISBN
        metadata = {
            "title": "Test Book",
            "creators": ["Author"],
            "identifiers": {"isbn": "1234567890"}
        }

        # When: We generate a unique ID
        unique_id = ImportService._generate_unique_id(metadata)

        # Then: The ID should be deterministic and use the ISBN
        # (Re-generating with same metadata should give same ID)
        unique_id2 = ImportService._generate_unique_id(metadata)
        assert unique_id == unique_id2

    def test_generate_unique_id_ensures_uniqueness(self):
        """Test that unique ID generation produces different IDs for different books."""
        # Given: Two different books without ISBNs
        metadata1 = {
            "title": "Test Book One",
            "creators": ["Author One"]
        }
        metadata2 = {
            "title": "Test Book Two",
            "creators": ["Author Two"]
        }

        # When: We generate unique IDs for both
        unique_id1 = ImportService._generate_unique_id(metadata1)
        unique_id2 = ImportService._generate_unique_id(metadata2)

        # Then: Different books should have different IDs
        assert unique_id1 != unique_id2

        # And: Same book should always get the same ID (deterministic)
        unique_id1_repeat = ImportService._generate_unique_id(metadata1)
        assert unique_id1 == unique_id1_repeat

    def test_get_sort_title(self):
        """Test sort title generation."""
        assert ImportService._get_sort_title("The Great Gatsby") == "Great Gatsby"
        assert ImportService._get_sort_title("A Tale of Two Cities") == "Tale of Two Cities"
        assert ImportService._get_sort_title("An Introduction") == "Introduction"
        assert ImportService._get_sort_title("Simple Title") == "Simple Title"

    def test_get_sort_name_enables_alphabetic_sorting(self):
        """Test that sort names enable correct alphabetical sorting by last name."""
        # Given: A list of authors
        authors = ["John Doe", "Alice Brown", "Bob Anderson"]

        # When: We generate sort names for each
        sort_names = [ImportService._get_sort_name(name) for name in authors]

        # Then: Sorting by sort_name should order by last name
        sorted_names = sorted(sort_names)
        assert sorted_names[0].startswith("Anderson")  # Anderson first
        assert sorted_names[1].startswith("Brown")     # Brown second
        assert sorted_names[2].startswith("Doe")       # Doe third

        # And: Single-name authors should sort by their single name
        single_name_sort = ImportService._get_sort_name("Madonna")
        assert single_name_sort == "Madonna"

    def test_create_book_with_metadata(self, temp_library):
        """Test creating book with comprehensive metadata."""
        service = temp_library.import_service

        metadata = {
            "title": "Test Book",
            "subtitle": "A Test Subtitle",
            "creators": ["Author One", "Author Two"],
            "subjects": ["Subject1", "Subject2"],
            "language": "en",
            "publisher": "Test Publisher",
            "date": "2023",
            "description": "Test description",
            "page_count": 200,
            "identifiers": {"isbn": "1234567890", "doi": "10.1234/test"}
        }

        unique_id = service._generate_unique_id(metadata)
        book = service._create_book(metadata, unique_id)

        assert book.title == "Test Book"
        assert book.subtitle == "A Test Subtitle"
        assert book.language == "en"
        assert book.publisher == "Test Publisher"
        assert len(book.authors) == 2
        assert len(book.subjects) == 2
        assert book.personal is not None
        assert book.personal.reading_status == "unread"

    def test_import_file_different_formats(self, temp_library):
        """Test that different format files create different file entries."""
        # Create first file
        test_file1 = temp_library.library_path / "test.txt"
        test_file1.write_text("Test content version 1")

        book1 = temp_library.add_book(
            test_file1,
            metadata={"title": "Same Book", "creators": ["Author"]},
            extract_text=False,
            extract_cover=False
        )

        # Create different file with same metadata but different content
        test_file2 = temp_library.library_path / "test.md"
        test_file2.write_text("Test content version 2 - different format")

        book2 = temp_library.add_book(
            test_file2,
            metadata={"title": "Same Book", "creators": ["Author"]},
            extract_text=False,
            extract_cover=False
        )

        # Should be same book, but with two different files
        assert book1.id == book2.id
        assert len(book2.files) == 2

    def test_import_with_identifiers(self, temp_library):
        """Test importing book with identifiers."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test content")

        book = temp_library.add_book(
            test_file,
            metadata={
                "title": "Book with ISBN",
                "creators": ["Author"],
                "identifiers": {"isbn": "978-1234567890", "doi": "10.1234/test"}
            },
            extract_text=False,
            extract_cover=False
        )

        assert len(book.identifiers) == 2
        schemes = {i.scheme for i in book.identifiers}
        assert "isbn" in schemes
        assert "doi" in schemes

    def test_get_file_path(self, temp_library):
        """Test file path generation with hash prefix."""
        service = temp_library.import_service
        file_hash = "abcdef123456789"

        file_path = service._get_file_path(file_hash, ".pdf")
        assert "files/ab" in str(file_path)
        assert file_path.name == f"{file_hash}.pdf"

    def test_get_cover_path(self, temp_library):
        """Test cover path generation."""
        service = temp_library.import_service
        file_hash = "fedcba987654321"

        cover_path = service._get_cover_path(file_hash, "jpg")
        assert "covers/fe" in str(cover_path)
        assert cover_path.name == f"{file_hash}.jpg"


class TestTextExtractionService:
    """Test text extraction service."""

    def test_text_extraction_service_creation(self, temp_library):
        """Test creating text extraction service."""
        service = TextExtractionService(temp_library.library_path)
        assert service is not None
        assert service.library_root == temp_library.library_path

    def test_extract_plaintext(self, temp_library):
        """Test extracting text from plain text file."""
        service = temp_library.text_service

        test_file = temp_library.library_path / "test.txt"
        content = "This is a test file with some text content."
        test_file.write_text(content)

        extracted = service._extract_plaintext(test_file)
        assert extracted == content

    def test_extract_plaintext_encoding_fallback(self, temp_library):
        """Test plaintext extraction with encoding fallback."""
        service = temp_library.text_service

        test_file = temp_library.library_path / "test_latin.txt"
        # Write with latin-1 encoding
        test_file.write_bytes(b"Test with special chars: \xe9\xe0\xf1")

        # Should fallback to latin-1 when utf-8 fails
        extracted = service._extract_plaintext(test_file)
        assert extracted is not None
        assert len(extracted) > 0

    def test_clean_text(self, temp_library):
        """Test text cleaning."""
        service = temp_library.text_service

        dirty_text = "Test    text  with\n\n\n\nexcessive   whitespace\n\n1\n2\n3"
        cleaned = service._clean_text(dirty_text)

        assert "    " not in cleaned
        assert "\n\n\n" not in cleaned

    def test_hash_text_detects_content_changes(self, temp_library):
        """Test that text hashing detects when content has changed."""
        # Given: A text extraction service
        service = temp_library.text_service

        # When: We hash the same text twice
        text = "Test content for hashing"
        text_hash1 = service._hash_text(text)
        text_hash2 = service._hash_text(text)

        # Then: Same text should produce the same hash (for cache hit detection)
        assert text_hash1 == text_hash2

        # And: Different text should produce different hashes (for change detection)
        modified_text = "Test content for hashing - modified"
        modified_hash = service._hash_text(modified_text)
        assert modified_hash != text_hash1

    def test_get_word_count(self, temp_library):
        """Test word count calculation."""
        service = temp_library.text_service

        text = "This is a test with five words"
        count = service.get_word_count(text)
        assert count == 7

    def test_create_chunks(self, temp_library):
        """Test creating text chunks."""
        service = temp_library.text_service

        # Create long text
        words = ["word"] * 1000
        long_text = " ".join(words)

        # Create a file and extracted text
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file = book.files[0]
        extracted = ExtractedText(
            file_id=file.id,
            content=long_text,
            content_hash=service._hash_text(long_text)
        )
        temp_library.session.add(extracted)
        temp_library.session.flush()

        chunks = service.create_chunks(extracted, file, temp_library.session, chunk_size=500, overlap=100)

        assert len(chunks) > 1
        assert all(chunk.file_id == file.id for chunk in chunks)
        assert all(chunk.has_embedding == False for chunk in chunks)

    def test_create_chunks_small_text(self, temp_library):
        """Test chunking with small text."""
        service = temp_library.text_service

        short_text = "Short text"

        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file = book.files[0]
        extracted = ExtractedText(
            file_id=file.id,
            content=short_text,
            content_hash=service._hash_text(short_text)
        )
        temp_library.session.add(extracted)
        temp_library.session.flush()

        chunks = service.create_chunks(extracted, file, temp_library.session)

        # Short text should produce 0 chunks (below 50 char threshold)
        assert len(chunks) == 0

    def test_extract_full_text_unsupported_format(self, temp_library):
        """Test extraction with unsupported format."""
        service = temp_library.text_service

        test_file = temp_library.library_path / "test.unknown"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file = book.files[0]
        # Manually set format to unsupported
        file.format = "unknown"

        result = service.extract_full_text(file, temp_library.session)
        assert result is None

    def test_extract_full_text_too_short(self, temp_library):
        """Test extraction with text that's too short."""
        test_file = temp_library.library_path / "short.txt"
        test_file.write_text("Hi")  # Very short

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        service = temp_library.text_service
        file = book.files[0]

        result = service.extract_full_text(file, temp_library.session)
        # Should return None because text is too short (< 100 chars)
        assert result is None

    def test_extract_full_text_missing_file(self, temp_library):
        """Test extraction when file doesn't exist."""
        service = temp_library.text_service

        # Create a file record without actual file
        test_file = temp_library.library_path / "exists.txt"
        test_file.write_text("Test")

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file = book.files[0]

        # Delete the physical file
        (temp_library.library_path / file.path).unlink()

        result = service.extract_full_text(file, temp_library.session)
        assert result is None

    def test_extract_and_chunk_all(self, temp_library):
        """Test combined extraction and chunking."""
        # Create a text file with enough content
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("This is a test book. " * 100)  # Make it long enough

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book", "creators": ["Test Author"]},
            extract_text=False
        )

        file = book.files[0]
        service = temp_library.text_service

        extracted, chunks = service.extract_and_chunk_all(file, temp_library.session)

        assert extracted is not None
        assert len(extracted.content) > 100
        assert len(chunks) >= 1

    def test_extract_and_chunk_all_failure(self, temp_library):
        """Test extract_and_chunk_all when extraction fails."""
        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("x")  # Too short

        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test", "creators": ["Author"]},
            extract_text=False
        )

        file = book.files[0]
        service = temp_library.text_service

        extracted, chunks = service.extract_and_chunk_all(file, temp_library.session)

        assert extracted is None
        assert chunks == []


class TestCoverExtraction:
    """Test cover extraction functionality."""

    @patch('fitz.open')
    def test_extract_pdf_cover_success(self, mock_fitz_open, temp_library):
        """Test PDF cover extraction."""
        service = temp_library.import_service

        # Mock PyMuPDF
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()

        mock_doc.__len__ = lambda self: 1
        mock_doc.__getitem__ = lambda self, idx: mock_page
        mock_page.get_pixmap.return_value = mock_pix
        mock_fitz_open.return_value = mock_doc

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        file_hash = "abc123"
        result = service._extract_pdf_cover(test_pdf, file_hash)

        assert result is not None
        assert "covers/ab" in str(result)

    @patch('fitz.open')
    def test_extract_pdf_cover_error(self, mock_fitz_open, temp_library):
        """Test PDF cover extraction with error."""
        service = temp_library.import_service

        mock_fitz_open.side_effect = Exception("PyMuPDF error")

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service._extract_pdf_cover(test_pdf, "hash123")
        assert result is None

    def test_create_thumbnail(self, temp_library):
        """Test thumbnail creation."""
        from PIL import Image

        service = temp_library.import_service

        # Create a test image
        cover_path = temp_library.library_path / "test_cover.jpg"
        img = Image.new('RGB', (400, 600), color='red')
        img.save(cover_path)

        file_hash = "test_hash"
        thumb_path = service._create_thumbnail(cover_path, file_hash)

        assert thumb_path.exists()
        assert thumb_path.name == f"{file_hash}_thumb.jpg"

        # Verify thumbnail is smaller
        thumb_img = Image.open(thumb_path)
        assert thumb_img.width <= 200
        assert thumb_img.height <= 300


class TestBatchImportWithErrors:
    """Test batch import with error scenarios."""

    def test_batch_import_partial_success(self, temp_library):
        """Test batch import where some files fail."""
        files_and_metadata = []

        # Valid file
        test_file1 = temp_library.library_path / "valid.txt"
        test_file1.write_text("Valid content")
        files_and_metadata.append((
            test_file1,
            {"title": "Valid Book", "creators": ["Author"]}
        ))

        # Invalid file (doesn't exist)
        files_and_metadata.append((
            Path("/nonexistent/file.txt"),
            {"title": "Invalid Book", "creators": ["Author"]}
        ))

        # Another valid file
        test_file2 = temp_library.library_path / "valid2.txt"
        test_file2.write_text("Valid content 2")
        files_and_metadata.append((
            test_file2,
            {"title": "Valid Book 2", "creators": ["Author"]}
        ))

        books = temp_library.batch_import(files_and_metadata, show_progress=False)

        # Should import only the valid files
        assert len(books) == 2


class TestPDFTextExtraction:
    """Test PDF text extraction with fallback."""

    @patch('fitz.open')
    def test_extract_pdf_with_pymupdf_success(self, mock_fitz_open, temp_library):
        """Test PDF text extraction with PyMuPDF."""
        service = temp_library.text_service

        # Mock PyMuPDF
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Text from PyMuPDF extraction"
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_fitz_open.return_value = mock_doc

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service._extract_pdf_text(test_pdf)

        assert "PyMuPDF" in result
        mock_doc.close.assert_called_once()

    @patch('fitz.open')
    @patch('pypdf.PdfReader')
    def test_extract_pdf_fallback_to_pypdf(self, mock_pypdf, mock_fitz_open, temp_library):
        """Test PDF text extraction fallback to pypdf."""
        service = temp_library.text_service

        # Make PyMuPDF fail
        mock_fitz_open.side_effect = Exception("PyMuPDF error")

        # Mock pypdf
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Text from pypdf"
        mock_reader.pages = [mock_page]
        mock_pypdf.return_value = mock_reader

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service._extract_pdf_text(test_pdf)

        assert "pypdf" in result

    @patch('fitz.open')
    @patch('pypdf.PdfReader')
    def test_extract_pdf_both_fail(self, mock_pypdf, mock_fitz_open, temp_library):
        """Test PDF extraction when both methods fail."""
        service = temp_library.text_service

        # Make both fail
        mock_fitz_open.side_effect = Exception("PyMuPDF error")
        mock_pypdf.side_effect = Exception("pypdf error")

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service._extract_pdf_text(test_pdf)

        assert result == ""


class TestEPUBTextExtraction:
    """Test EPUB text extraction."""

    @patch('ebooklib.epub.read_epub')
    def test_extract_epub_error(self, mock_read_epub, temp_library):
        """Test EPUB extraction with error."""
        service = temp_library.text_service

        mock_read_epub.side_effect = Exception("EPUB read error")

        test_epub = temp_library.library_path / "test.epub"
        test_epub.write_text("fake epub")

        result = service._extract_epub_text(test_epub)

        assert result == ""


class TestPageExtraction:
    """Test page-specific extraction."""

    @patch('fitz.open')
    def test_extract_page_content(self, mock_fitz_open, temp_library):
        """Test extracting specific page from PDF."""
        service = temp_library.text_service

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 content"
        mock_doc.__len__ = lambda self: 5
        mock_doc.__getitem__ = lambda self, idx: mock_page

        mock_fitz_open.return_value = mock_doc

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service.extract_page_content(test_pdf, 0)

        assert "Page 1" in result
        mock_doc.close.assert_called()

    @patch('fitz.open')
    def test_extract_page_content_out_of_range(self, mock_fitz_open, temp_library):
        """Test extracting page out of range."""
        service = temp_library.text_service

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 5
        mock_fitz_open.return_value = mock_doc

        test_pdf = temp_library.library_path / "test.pdf"
        test_pdf.write_text("fake pdf")

        result = service.extract_page_content(test_pdf, 100)

        assert result is None

    def test_extract_page_content_non_pdf(self, temp_library):
        """Test extracting page from non-PDF."""
        service = temp_library.text_service

        test_file = temp_library.library_path / "test.txt"
        test_file.write_text("not a pdf")

        result = service.extract_page_content(test_file, 0)

        assert result is None


class TestEPUBCoverExtraction:
    """Test EPUB cover extraction error handling."""

    @patch('ebooklib.epub.read_epub')
    def test_extract_epub_cover_error(self, mock_read_epub, temp_library):
        """Test EPUB cover extraction with error."""
        service = temp_library.import_service

        mock_read_epub.side_effect = Exception("EPUB read error")

        test_epub = temp_library.library_path / "test.epub"
        test_epub.write_text("fake epub")

        result = service._extract_epub_cover(test_epub, "test_hash")

        assert result is None
