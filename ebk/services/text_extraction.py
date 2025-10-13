"""
Text extraction service for ebook files.

Handles extraction from PDF, EPUB, TXT, MD and stores in database with FTS indexing.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple
import logging

import pypdf
import fitz  # PyMuPDF
from ebooklib import epub
from bs4 import BeautifulSoup

from ..db.models import File, ExtractedText, TextChunk
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class TextExtractionService:
    """Service for extracting and chunking text from ebook files."""

    def __init__(self, library_root: Path):
        self.library_root = Path(library_root)

    def extract_full_text(self, file: File, session: Session) -> Optional[ExtractedText]:
        """
        Extract complete text from ebook file and store in database.

        Args:
            file: File model instance
            session: Database session

        Returns:
            ExtractedText instance or None if extraction failed
        """
        file_path = self.library_root / file.path

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            # Extract based on format
            if file.format.lower() in ['txt', 'md', 'text']:
                text = self._extract_plaintext(file_path)
            elif file.format.lower() == 'pdf':
                text = self._extract_pdf_text(file_path)
            elif file.format.lower() == 'epub':
                text = self._extract_epub_text(file_path)
            else:
                logger.warning(f"Unsupported format for text extraction: {file.format}")
                return None

            if not text or len(text.strip()) < 100:
                logger.warning(f"Extracted text too short for {file.path}")
                return None

            # Store in database
            extracted = ExtractedText(
                file_id=file.id,
                content=text,
                content_hash=self._hash_text(text)
            )
            session.add(extracted)

            # Update file status
            file.text_extracted = True
            file.extraction_date = extracted.extracted_at

            # Update FTS index
            self._update_fts_index(session, file.book_id, text)

            logger.info(f"Extracted {len(text)} chars from {file.path}")
            return extracted

        except Exception as e:
            logger.error(f"Error extracting text from {file.path}: {e}")
            return None

    def create_chunks(self, extracted: ExtractedText, file: File,
                     session: Session, chunk_size: int = 500,
                     overlap: int = 100) -> List[TextChunk]:
        """
        Split extracted text into overlapping chunks for semantic search.

        Args:
            extracted: ExtractedText instance
            file: File instance
            session: Database session
            chunk_size: Number of words per chunk
            overlap: Number of overlapping words between chunks

        Returns:
            List of TextChunk instances
        """
        text = extracted.content
        words = text.split()

        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)

            if len(chunk_text.strip()) < 50:  # Skip tiny chunks
                continue

            chunk = TextChunk(
                file_id=file.id,
                chunk_index=len(chunks),
                content=chunk_text,
                has_embedding=False
            )
            chunks.append(chunk)

        session.add_all(chunks)
        logger.info(f"Created {len(chunks)} chunks from {file.path}")
        return chunks

    def _extract_plaintext(self, file_path: Path) -> str:
        """Extract text from plain text files."""
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with different encoding
            return file_path.read_text(encoding='latin-1')

    def _extract_pdf_text(self, file_path: Path) -> str:
        """
        Extract text from PDF using PyMuPDF (primary) with pypdf fallback.
        """
        try:
            # Try PyMuPDF first (better quality)
            doc = fitz.open(str(file_path))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            if text.strip():
                return self._clean_text(text)

        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}, trying pypdf")

        try:
            # Fallback to pypdf
            with open(file_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()

            return self._clean_text(text)

        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""

    def _extract_epub_text(self, file_path: Path) -> str:
        """Extract text from EPUB file."""
        try:
            book = epub.read_epub(str(file_path))
            text_parts = []

            for item in book.get_items():
                # Handle different ebooklib versions
                # Type 9 is ITEM_DOCUMENT in ebooklib
                item_type = item.get_type()

                # Check if this is a document item (HTML/XHTML content)
                is_document = False
                if hasattr(epub, 'ITEM_DOCUMENT'):
                    is_document = item_type == epub.ITEM_DOCUMENT
                else:
                    # Fallback: type 9 is document, or check media type
                    is_document = (item_type == 9 or
                                 'html' in item.get_name().lower() or
                                 (hasattr(item, 'media_type') and
                                  item.media_type and
                                  'html' in item.media_type.lower()))

                if is_document:
                    try:
                        soup = BeautifulSoup(item.content, 'html.parser')

                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()

                        text = soup.get_text(separator='\n')
                        text_parts.append(text)
                    except Exception as e:
                        logger.debug(f"Failed to extract text from item {item.get_name()}: {e}")
                        continue

            full_text = '\n\n'.join(text_parts)
            return self._clean_text(full_text)

        except Exception as e:
            logger.error(f"EPUB text extraction failed: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        # Remove page headers/footers (common patterns)
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _hash_text(self, text: str) -> str:
        """Generate hash of text content."""
        import hashlib
        return hashlib.sha256(text.encode()).hexdigest()

    def _update_fts_index(self, session: Session, book_id: int, extracted_text: str):
        """
        Update full-text search index.

        Args:
            session: Database session
            book_id: Book ID
            extracted_text: Extracted text content
        """
        try:
            # Get book title and description for FTS
            from ..db.models import Book
            book = session.query(Book).get(book_id)

            if not book:
                return

            # Delete existing FTS entry if exists
            session.execute(
                text("DELETE FROM books_fts WHERE book_id = :book_id"),
                {"book_id": book_id}
            )

            # Insert into FTS table
            session.execute(
                text("""
                INSERT INTO books_fts (book_id, title, description, extracted_text)
                VALUES (:book_id, :title, :description, :extracted_text)
                """),
                {
                    "book_id": book_id,
                    "title": book.title or '',
                    "description": book.description or '',
                    "extracted_text": extracted_text[:50000]  # Limit FTS content to first 50k chars
                }
            )

            logger.info(f"Updated FTS index for book {book_id}")

        except Exception as e:
            logger.error(f"Error updating FTS index: {e}")

    def extract_page_content(self, file_path: Path, page_number: int) -> Optional[str]:
        """
        Extract text from a specific page (PDF only).

        Args:
            file_path: Path to PDF file
            page_number: Page number (0-indexed)

        Returns:
            Page text or None
        """
        try:
            if file_path.suffix.lower() == '.pdf':
                doc = fitz.open(str(file_path))
                if 0 <= page_number < len(doc):
                    page_text = doc[page_number].get_text()
                    doc.close()
                    return self._clean_text(page_text)
                doc.close()
        except Exception as e:
            logger.error(f"Error extracting page {page_number}: {e}")

        return None

    def get_word_count(self, text: str) -> int:
        """Get word count from text."""
        return len(text.split())

    def extract_and_chunk_all(self, file: File, session: Session,
                              chunk_size: int = 500) -> Tuple[Optional[ExtractedText], List[TextChunk]]:
        """
        Extract full text and create chunks in one operation.

        Args:
            file: File instance
            session: Database session
            chunk_size: Words per chunk

        Returns:
            Tuple of (ExtractedText, List[TextChunk])
        """
        extracted = self.extract_full_text(file, session)

        if not extracted:
            return None, []

        chunks = self.create_chunks(extracted, file, session, chunk_size)

        return extracted, chunks
