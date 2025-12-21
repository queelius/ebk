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
