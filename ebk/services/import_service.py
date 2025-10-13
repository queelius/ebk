"""
Import service for adding books to the database.

Handles file copying, deduplication, metadata extraction, and text indexing.
"""

import shutil
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from PIL import Image

from ..db.models import Book, Author, Subject, Identifier, File, Cover, PersonalMetadata
from ..db.session import get_or_create
from .text_extraction import TextExtractionService

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing books into the library."""

    def __init__(self, library_root: Path, session: Session):
        self.library_root = Path(library_root)
        self.session = session
        self.text_service = TextExtractionService(library_root)

        # Create directory structure
        (self.library_root / 'files').mkdir(parents=True, exist_ok=True)
        (self.library_root / 'covers').mkdir(parents=True, exist_ok=True)
        (self.library_root / 'covers' / 'thumbnails').mkdir(exist_ok=True)

    def import_file(self, source_path: Path, metadata: Dict[str, Any],
                   extract_text: bool = True, extract_cover: bool = True) -> Optional[Book]:
        """
        Import a single ebook file into the library.

        Args:
            source_path: Path to source ebook file
            metadata: Metadata dictionary
            extract_text: Whether to extract full text
            extract_cover: Whether to extract cover image

        Returns:
            Book instance or None if import failed
        """
        source_path = Path(source_path)

        if not source_path.exists():
            logger.error(f"Source file not found: {source_path}")
            return None

        try:
            # Compute file hash
            file_hash = self._compute_file_hash(source_path)

            # Check for duplicate by hash
            existing_file = self.session.query(File).filter_by(file_hash=file_hash).first()
            if existing_file:
                logger.info(f"Duplicate file detected (hash match): {source_path.name}")
                return existing_file.book

            # Generate unique ID for book
            unique_id = self._generate_unique_id(metadata)

            # Check if book already exists by unique_id
            existing_book = self.session.query(Book).filter_by(unique_id=unique_id).first()

            if existing_book:
                # Add this file format to existing book
                logger.info(f"Adding format to existing book: {metadata.get('title')}")
                book = existing_book
            else:
                # Create new book
                book = self._create_book(metadata, unique_id)

            # Copy file to library
            dest_path = self._get_file_path(file_hash, source_path.suffix)
            shutil.copy2(source_path, dest_path)

            # Get file metadata from filesystem
            file_stat = source_path.stat()
            import mimetypes
            from datetime import datetime
            mime_type = mimetypes.guess_type(str(source_path))[0]
            created_date = datetime.fromtimestamp(file_stat.st_ctime)
            modified_date = datetime.fromtimestamp(file_stat.st_mtime)

            # Extract creator application from metadata if PDF
            creator_app = metadata.get('creator_application')

            # Create file record with enhanced metadata
            file = File(
                book_id=book.id,
                path=str(dest_path.relative_to(self.library_root)),
                format=source_path.suffix[1:].lower(),  # Remove leading dot
                size_bytes=file_stat.st_size,
                file_hash=file_hash,
                mime_type=mime_type,
                created_date=created_date,
                modified_date=modified_date,
                creator_application=creator_app
            )
            self.session.add(file)
            self.session.flush()  # Get file.id

            # Extract cover if needed
            if extract_cover:
                self._extract_cover(source_path, book, file)

            # Extract text if needed
            if extract_text:
                self.text_service.extract_and_chunk_all(file, self.session)

            self.session.commit()
            logger.info(f"Successfully imported: {metadata.get('title')}")
            return book

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error importing {source_path}: {e}")
            return None

    def _create_book(self, metadata: Dict[str, Any], unique_id: str) -> Book:
        """Create book record with metadata."""

        # Create book with enhanced metadata
        book = Book(
            unique_id=unique_id,
            title=metadata.get('title', 'Unknown Title'),
            subtitle=metadata.get('subtitle'),
            sort_title=self._get_sort_title(metadata.get('title', '')),
            language=metadata.get('language', 'en'),
            publisher=metadata.get('publisher'),
            publication_date=metadata.get('date'),
            description=metadata.get('description'),
            page_count=metadata.get('page_count'),
            # New fields
            series=metadata.get('series'),
            series_index=metadata.get('series_index'),
            edition=metadata.get('edition'),
            rights=metadata.get('rights'),
            source=metadata.get('source'),
            keywords=metadata.get('keywords')
        )
        self.session.add(book)
        self.session.flush()  # Get book.id

        # Add authors
        creators = metadata.get('creators') or []
        for author_name in creators:
            if author_name:  # Skip None/empty values
                author, _ = get_or_create(
                    self.session,
                    Author,
                    name=author_name,
                    sort_name=self._get_sort_name(author_name)
                )
                book.authors.append(author)

        # Add subjects/tags
        subjects = metadata.get('subjects') or []
        for subject_name in subjects:
            if subject_name:  # Skip None/empty values
                subject, _ = get_or_create(
                    self.session,
                    Subject,
                    name=subject_name,
                    type='topic'
                )
                book.subjects.append(subject)

        # Add contributors (editors, translators, etc.)
        contributors = metadata.get('contributors') or []
        for contrib in contributors:
            if isinstance(contrib, dict):
                name = contrib.get('name')
                role = contrib.get('role', 'contributor')
                file_as = contrib.get('file_as', '')
                if name:
                    from ..db.models import Contributor
                    contributor = Contributor(
                        book_id=book.id,
                        name=name,
                        role=role,
                        file_as=file_as
                    )
                    self.session.add(contributor)

        # Add identifiers
        for scheme, value in metadata.get('identifiers', {}).items():
            identifier = Identifier(
                book_id=book.id,
                scheme=scheme,
                value=value
            )
            self.session.add(identifier)

        # Create personal metadata
        personal = PersonalMetadata(
            book_id=book.id,
            reading_status='unread',
            owned=True
        )
        self.session.add(personal)

        return book

    def _extract_cover(self, source_path: Path, book: Book, file: File):
        """Extract and save cover image."""
        cover_path = None

        try:
            if source_path.suffix.lower() == '.pdf':
                cover_path = self._extract_pdf_cover(source_path, file.file_hash)
            elif source_path.suffix.lower() == '.epub':
                cover_path = self._extract_epub_cover(source_path, file.file_hash)

            if cover_path and cover_path.exists():
                # Create thumbnail
                thumb_path = self._create_thumbnail(cover_path, file.file_hash)

                # Save cover record
                img = Image.open(cover_path)
                cover = Cover(
                    book_id=book.id,
                    path=str(cover_path.relative_to(self.library_root)),
                    width=img.width,
                    height=img.height,
                    is_primary=True,
                    source='extracted'
                )
                self.session.add(cover)
                logger.info(f"Extracted cover for {book.title}")

        except Exception as e:
            logger.warning(f"Cover extraction failed: {e}")

    def _extract_pdf_cover(self, pdf_path: Path, file_hash: str) -> Optional[Path]:
        """Extract first page of PDF as cover image."""
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for quality

                cover_path = self._get_cover_path(file_hash, 'png')
                pix.save(str(cover_path))
                doc.close()
                return cover_path
        except Exception as e:
            logger.error(f"PDF cover extraction error: {e}")

        return None

    def _extract_epub_cover(self, epub_path: Path, file_hash: str) -> Optional[Path]:
        """Extract cover image from EPUB."""
        try:
            from ebooklib import epub
            book = epub.read_epub(str(epub_path))

            # Try to get cover - handle different ebooklib versions
            cover_item = None

            # Method 1: Try ITEM_COVER constant (older ebooklib)
            try:
                for item in book.get_items():
                    if hasattr(epub, 'ITEM_COVER') and item.get_type() == epub.ITEM_COVER:
                        cover_item = item
                        break
            except AttributeError:
                pass

            # Method 2: Look for image named 'cover' or check item type == 1 (image)
            if not cover_item:
                for item in book.get_items():
                    # Type 1 is ITEM_IMAGE in ebooklib
                    if item.get_type() == 1:  # ITEM_IMAGE
                        if 'cover' in item.get_name().lower():
                            cover_item = item
                            break

            # Method 3: Try ITEM_IMAGE constant fallback
            if not cover_item:
                try:
                    for item in book.get_items():
                        if hasattr(epub, 'ITEM_IMAGE') and item.get_type() == epub.ITEM_IMAGE:
                            if 'cover' in item.get_name().lower():
                                cover_item = item
                                break
                except AttributeError:
                    pass

            if cover_item:
                # Determine image format
                ext = Path(cover_item.get_name()).suffix or '.jpg'
                cover_path = self._get_cover_path(file_hash, ext[1:])

                cover_path.write_bytes(cover_item.get_content())
                return cover_path

        except Exception as e:
            logger.error(f"EPUB cover extraction error: {e}")

        return None

    def _create_thumbnail(self, cover_path: Path, file_hash: str) -> Path:
        """Create thumbnail from cover image."""
        thumb_path = self.library_root / 'covers' / 'thumbnails' / f"{file_hash}_thumb.jpg"

        try:
            img = Image.open(cover_path)
            img.thumbnail((200, 300))
            img.save(thumb_path, 'JPEG', quality=85)
            return thumb_path
        except Exception as e:
            logger.error(f"Thumbnail creation error: {e}")
            return cover_path

    def _get_file_path(self, file_hash: str, extension: str) -> Path:
        """Get storage path for file based on hash prefix."""
        prefix = file_hash[:2]
        dir_path = self.library_root / 'files' / prefix
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / f"{file_hash}{extension}"

    def _get_cover_path(self, file_hash: str, extension: str) -> Path:
        """Get storage path for cover based on hash prefix."""
        prefix = file_hash[:2]
        dir_path = self.library_root / 'covers' / prefix
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / f"{file_hash}.{extension}"

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(8192), b''):
                sha256.update(block)
        return sha256.hexdigest()

    @staticmethod
    def _generate_unique_id(metadata: Dict[str, Any]) -> str:
        """Generate unique ID for book based on metadata."""
        # Use ISBN if available
        identifiers = metadata.get('identifiers', {})
        if 'isbn' in identifiers:
            return f"isbn_{identifiers['isbn']}"

        # Otherwise use hash of title + authors
        title = metadata.get('title', 'unknown')
        authors = ','.join(metadata.get('creators', ['unknown']))
        content = f"{title}:{authors}".lower()
        return hashlib.md5(content.encode()).hexdigest()[:16]

    @staticmethod
    def _get_sort_title(title: str) -> str:
        """Get sortable title (remove leading articles)."""
        title = title.strip()
        for article in ['The ', 'A ', 'An ']:
            if title.startswith(article):
                return title[len(article):]
        return title

    @staticmethod
    def _get_sort_name(name: str) -> str:
        """Get sortable name (Last, First format)."""
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[-1]}, {' '.join(parts[:-1])}"
        return name

    def import_calibre_book(self, calibre_metadata_path: Path) -> Optional[Book]:
        """
        Import book from Calibre metadata.opf file.

        Args:
            calibre_metadata_path: Path to metadata.opf file

        Returns:
            Book instance or None
        """
        from ..extract_metadata import extract_metadata_from_opf

        metadata = extract_metadata_from_opf(str(calibre_metadata_path))

        # Find ebook files in same directory
        book_dir = calibre_metadata_path.parent
        ebook_files = list(book_dir.glob('*.pdf')) + \
                     list(book_dir.glob('*.epub')) + \
                     list(book_dir.glob('*.mobi'))

        if not ebook_files:
            logger.warning(f"No ebook files found in {book_dir}")
            return None

        # Import first file (others will be added as formats)
        book = self.import_file(ebook_files[0], metadata)

        # Import additional formats
        for ebook_file in ebook_files[1:]:
            self.import_file(ebook_file, metadata, extract_text=False, extract_cover=False)

        return book

    def batch_import(self, file_paths: List[Path], metadata_list: List[Dict[str, Any]],
                    show_progress: bool = False) -> List[Book]:
        """
        Import multiple files with progress tracking.

        Args:
            file_paths: List of file paths to import
            metadata_list: List of metadata dicts (one per file)
            show_progress: Whether to show progress bar

        Returns:
            List of imported Book instances
        """
        books = []

        if show_progress:
            from rich.progress import Progress
            with Progress() as progress:
                task = progress.add_task("[green]Importing...", total=len(file_paths))
                for file_path, metadata in zip(file_paths, metadata_list):
                    book = self.import_file(file_path, metadata)
                    if book:
                        books.append(book)
                    progress.advance(task)
        else:
            for file_path, metadata in zip(file_paths, metadata_list):
                book = self.import_file(file_path, metadata)
                if book:
                    books.append(book)

        return books
