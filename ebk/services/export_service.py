"""
Export service for library data.

Provides a unified interface for exporting library data in various formats:
- JSON: Machine-readable data export
- CSV: Spreadsheet-compatible format
- HTML: Standalone web interface
- OPDS: E-reader compatible catalog
"""

import json
import csv
import io
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..db.models import Book

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting library data in various formats."""

    def __init__(self, session: Session, library_path: Optional[Path] = None):
        """
        Initialize the export service.

        Args:
            session: SQLAlchemy database session
            library_path: Path to the library root (needed for file copying)
        """
        self.session = session
        self.library_path = Path(library_path) if library_path else None

    def export_json(
        self,
        books: List[Book],
        include_annotations: bool = True,
        include_personal: bool = True,
        pretty: bool = True,
    ) -> str:
        """
        Export books to JSON format.

        Args:
            books: List of Book objects to export
            include_annotations: Include notes and annotations
            include_personal: Include ratings, favorites, reading status
            pretty: Pretty-print the JSON output

        Returns:
            JSON string representation of the books
        """
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_books": len(books),
            "books": []
        }

        for book in books:
            book_data = self._book_to_dict(book, include_annotations, include_personal)
            export_data["books"].append(book_data)

        if pretty:
            return json.dumps(export_data, indent=2, ensure_ascii=False)
        return json.dumps(export_data, ensure_ascii=False)

    def export_csv(
        self,
        books: List[Book],
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        Export books to CSV format.

        Args:
            books: List of Book objects to export
            fields: List of field names to include (None = default fields)

        Returns:
            CSV string representation of the books
        """
        if fields is None:
            fields = [
                "id", "title", "authors", "language", "publisher",
                "publication_date", "subjects", "formats", "rating",
                "favorite", "reading_status"
            ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for book in books:
            row = self._book_to_csv_row(book)
            writer.writerow(row)

        return output.getvalue()

    def export_html(
        self,
        books: List[Book],
        output_path: Path,
        include_stats: bool = True,
        base_url: str = "",
        views: Optional[List[Dict[str, Any]]] = None,
        copy_files: bool = False,
    ) -> Dict[str, Any]:
        """
        Export books to a standalone HTML file.

        Args:
            books: List of Book objects to export
            output_path: Path to output HTML file
            include_stats: Include library statistics
            base_url: Base URL for file links
            views: List of view definitions for sidebar
            copy_files: Copy ebook/cover files to output directory

        Returns:
            Dictionary with export statistics
        """
        from ..exports.html_library import export_to_html

        output_path = Path(output_path)
        stats = {
            "books": len(books),
            "files_copied": 0,
            "covers_copied": 0,
        }

        # Copy files if requested
        if copy_files and self.library_path:
            stats.update(self._copy_files(books, output_path.parent, base_url))

        # Export HTML
        export_to_html(
            books=books,
            output_path=output_path,
            include_stats=include_stats,
            base_url=base_url,
            views=views,
        )

        return stats

    def export_opds(
        self,
        books: List[Book],
        output_path: Path,
        title: str = "ebk Library",
        subtitle: str = "",
        base_url: str = "",
        copy_files: bool = False,
        copy_covers: bool = False,
    ) -> Dict[str, Any]:
        """
        Export books to an OPDS catalog file.

        Args:
            books: List of Book objects to export
            output_path: Path to output XML file
            title: Catalog title
            subtitle: Catalog subtitle
            base_url: Base URL for file/cover links
            copy_files: Copy ebook files to output directory
            copy_covers: Copy cover images to output directory

        Returns:
            Dictionary with export statistics
        """
        from ..exports.opds_export import export_to_opds

        if not self.library_path:
            raise ValueError("library_path required for OPDS export")

        return export_to_opds(
            books=books,
            output_path=output_path,
            library_path=self.library_path,
            title=title,
            subtitle=subtitle,
            base_url=base_url,
            copy_files=copy_files,
            copy_covers=copy_covers,
        )

    def get_views_data(
        self,
        books: List[Book],
        include_builtin: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get views data for export, with book IDs resolved.

        Args:
            books: List of books being exported
            include_builtin: Include builtin views

        Returns:
            List of view definitions with resolved book_ids
        """
        from ..views import ViewService

        views_svc = ViewService(self.session)
        all_views = views_svc.list(include_builtin=include_builtin)

        book_ids_set = {b.id for b in books}
        views_data = []

        for v in all_views:
            try:
                view_books = views_svc.evaluate(v['name'])
                view_book_ids = [tb.book.id for tb in view_books if tb.book.id in book_ids_set]
                if view_book_ids:
                    views_data.append({
                        'name': v['name'],
                        'description': v.get('description', ''),
                        'book_ids': view_book_ids,
                        'builtin': v.get('builtin', False)
                    })
            except Exception:
                pass  # Skip views that fail to evaluate

        return views_data

    def _book_to_dict(
        self,
        book: Book,
        include_annotations: bool = True,
        include_personal: bool = True,
    ) -> Dict[str, Any]:
        """Convert a Book object to a dictionary for export."""
        data = {
            "id": book.id,
            "unique_id": book.unique_id,
            "title": book.title,
            "subtitle": book.subtitle,
            "authors": [a.name for a in book.authors],
            "language": book.language,
            "publisher": book.publisher,
            "publication_date": book.publication_date,
            "description": book.description,
            "subjects": [s.name for s in book.subjects],
            "series": book.series,
            "series_index": book.series_index,
            "identifiers": {i.scheme: i.value for i in book.identifiers},
            "files": [
                {
                    "format": f.format,
                    "path": f.path,
                    "size_bytes": f.size_bytes,
                    "file_hash": f.file_hash,
                }
                for f in book.files
            ],
            "covers": [
                {
                    "path": c.path,
                    "width": c.width,
                    "height": c.height,
                    "is_primary": c.is_primary,
                }
                for c in book.covers
            ],
            "tags": [t.full_path for t in book.tags] if book.tags else [],
            "created_at": book.created_at.isoformat() if book.created_at else None,
            "updated_at": book.updated_at.isoformat() if book.updated_at else None,
        }

        if include_personal and book.personal:
            pm = book.personal
            data["personal"] = {
                "rating": pm.rating,
                "is_favorite": pm.favorite,
                "reading_status": pm.reading_status,
                "reading_progress": pm.reading_progress,
                "date_started": pm.date_started.isoformat() if pm.date_started else None,
                "date_finished": pm.date_finished.isoformat() if pm.date_finished else None,
                "personal_tags": pm.personal_tags or [],
                "queue_position": pm.queue_position,
            }

        if include_annotations:
            data["annotations"] = [
                {
                    "id": a.id,
                    "type": a.annotation_type,
                    "content": a.content,
                    "page": a.page_number,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in book.annotations
            ] if hasattr(book, 'annotations') and book.annotations else []

        return data

    def _book_to_csv_row(self, book: Book) -> Dict[str, Any]:
        """Convert a Book object to a CSV row dictionary."""
        pm = book.personal
        return {
            "id": book.id,
            "unique_id": book.unique_id,
            "title": book.title,
            "subtitle": book.subtitle or "",
            "authors": "; ".join(a.name for a in book.authors),
            "language": book.language or "",
            "publisher": book.publisher or "",
            "publication_date": book.publication_date or "",
            "description": (book.description or "")[:200],  # Truncate for CSV
            "subjects": "; ".join(s.name for s in book.subjects),
            "series": book.series or "",
            "series_index": book.series_index or "",
            "formats": ", ".join(f.format for f in book.files),
            "tags": "; ".join(t.full_path for t in book.tags) if book.tags else "",
            "rating": pm.rating if pm else "",
            "favorite": "yes" if pm and pm.favorite else "no",
            "reading_status": pm.reading_status if pm else "",
        }

    def export_goodreads_csv(self, books: List[Book]) -> str:
        """
        Export books to Goodreads-compatible CSV format.

        The exported CSV can be imported into Goodreads via their import feature.
        See: https://www.goodreads.com/review/import

        Args:
            books: List of Book objects to export

        Returns:
            CSV string in Goodreads format
        """
        # Goodreads CSV columns (required and optional)
        fields = [
            "Title", "Author", "Additional Authors", "ISBN", "ISBN13",
            "My Rating", "Average Rating", "Publisher", "Binding", "Number of Pages",
            "Year Published", "Original Publication Year", "Date Read", "Date Added",
            "Bookshelves", "Bookshelves with positions", "Exclusive Shelf",
            "My Review", "Spoiler", "Private Notes", "Read Count", "Owned Copies"
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for book in books:
            pm = book.personal

            # Get authors
            authors = list(book.authors)
            primary_author = authors[0].name if authors else ""
            additional_authors = ", ".join(a.name for a in authors[1:]) if len(authors) > 1 else ""

            # Get identifiers
            identifiers = {i.scheme.lower(): i.value for i in book.identifiers}
            isbn = identifiers.get('isbn', '')
            isbn13 = identifiers.get('isbn13', '')

            # Map reading status to Goodreads exclusive shelf
            status_map = {
                'read': 'read',
                'reading': 'currently-reading',
                'to_read': 'to-read',
                'unread': 'to-read',
                'abandoned': 'read',  # No abandoned shelf in Goodreads
                'reference': 'read',
            }
            status = pm.reading_status if pm else 'unread'
            exclusive_shelf = status_map.get(status, 'to-read')

            # Convert rating (ebk uses 0-5, Goodreads uses 1-5)
            rating = ""
            if pm and pm.rating:
                # Round to integer, minimum 1
                rating = str(max(1, round(pm.rating)))

            # Get bookshelves (tags)
            bookshelves = []
            if book.tags:
                bookshelves.extend(t.name for t in book.tags)
            if pm and pm.personal_tags:
                bookshelves.extend(pm.personal_tags)

            # Format dates
            date_read = ""
            date_added = ""
            if pm:
                if pm.date_finished:
                    date_read = pm.date_finished.strftime("%Y/%m/%d")
                if book.created_at:
                    date_added = book.created_at.strftime("%Y/%m/%d")

            # Parse publication year
            pub_year = ""
            if book.publication_date:
                # Try to extract year from various formats
                pub_date = book.publication_date
                if len(pub_date) >= 4 and pub_date[:4].isdigit():
                    pub_year = pub_date[:4]

            row = {
                "Title": book.title or "",
                "Author": primary_author,
                "Additional Authors": additional_authors,
                "ISBN": isbn,
                "ISBN13": isbn13,
                "My Rating": rating,
                "Average Rating": "",  # We don't have this
                "Publisher": book.publisher or "",
                "Binding": "",  # Could map from file format
                "Number of Pages": str(book.page_count) if book.page_count else "",
                "Year Published": pub_year,
                "Original Publication Year": pub_year,
                "Date Read": date_read,
                "Date Added": date_added,
                "Bookshelves": ", ".join(bookshelves),
                "Bookshelves with positions": "",
                "Exclusive Shelf": exclusive_shelf,
                "My Review": "",  # Could add from annotations
                "Spoiler": "",
                "Private Notes": "",
                "Read Count": "1" if status == 'read' else "0",
                "Owned Copies": "1",
            }
            writer.writerow(row)

        return output.getvalue()

    def export_calibre_csv(self, books: List[Book]) -> str:
        """
        Export books to Calibre-compatible CSV format.

        The exported CSV can be imported into Calibre using the "Add books" >
        "Add from ISBN" or via calibredb command-line tool.

        Args:
            books: List of Book objects to export

        Returns:
            CSV string in Calibre format
        """
        # Calibre CSV columns
        fields = [
            "title", "authors", "author_sort", "publisher", "pubdate",
            "languages", "rating", "tags", "series", "series_index",
            "identifiers", "comments", "isbn"
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for book in books:
            pm = book.personal

            # Get authors
            authors = " & ".join(a.name for a in book.authors)
            # Author sort: "Last, First & Last, First"
            author_sort_parts = []
            for a in book.authors:
                parts = a.name.split()
                if len(parts) >= 2:
                    author_sort_parts.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
                else:
                    author_sort_parts.append(a.name)
            author_sort = " & ".join(author_sort_parts)

            # Get identifiers in Calibre format: isbn:123,asin:B00...
            identifiers = {i.scheme.lower(): i.value for i in book.identifiers}
            id_str = ",".join(f"{k}:{v}" for k, v in identifiers.items())
            isbn = identifiers.get('isbn', identifiers.get('isbn13', ''))

            # Collect tags
            tags_list = []
            if book.subjects:
                tags_list.extend(s.name for s in book.subjects)
            if book.tags:
                tags_list.extend(t.full_path for t in book.tags)
            if pm and pm.personal_tags:
                tags_list.extend(pm.personal_tags)
            # Add reading status as tag
            if pm and pm.reading_status:
                tags_list.append(f"status:{pm.reading_status}")
            if pm and pm.favorite:
                tags_list.append("favorite")

            # Convert rating (ebk uses 0-5, Calibre uses 0-10)
            rating = ""
            if pm and pm.rating:
                rating = str(int(pm.rating * 2))

            # Language codes
            language = book.language or ""

            # Series info
            series = book.series or ""
            series_index = str(book.series_index) if book.series_index else ""

            # Description/comments
            comments = book.description or ""

            row = {
                "title": book.title or "",
                "authors": authors,
                "author_sort": author_sort,
                "publisher": book.publisher or "",
                "pubdate": book.publication_date or "",
                "languages": language,
                "rating": rating,
                "tags": ", ".join(tags_list),
                "series": series,
                "series_index": series_index,
                "identifiers": id_str,
                "comments": comments,
                "isbn": isbn,
            }
            writer.writerow(row)

        return output.getvalue()

    def _copy_files(
        self,
        books: List[Book],
        output_dir: Path,
        base_url: str,
    ) -> Dict[str, int]:
        """
        Copy ebook and cover files to output directory.

        Returns statistics about copied files.
        """
        if not self.library_path:
            return {"files_copied": 0, "covers_copied": 0}

        # Determine copy destination
        copy_dest = output_dir / base_url.lstrip('/') if base_url else output_dir
        copy_dest.mkdir(parents=True, exist_ok=True)

        files_copied = 0
        covers_copied = 0
        total_size = 0

        for book in books:
            # Copy ebook files
            for file in book.files:
                src = self.library_path / file.path
                dest = copy_dest / file.path

                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    files_copied += 1
                    total_size += file.size_bytes or 0

            # Copy cover images
            for cover in book.covers:
                src = self.library_path / cover.path
                dest = copy_dest / cover.path

                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    covers_copied += 1
                    total_size += src.stat().st_size

        return {
            "files_copied": files_copied,
            "covers_copied": covers_copied,
            "total_size_bytes": total_size,
        }
