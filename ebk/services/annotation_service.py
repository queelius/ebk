"""
Annotation service for managing book annotations.

Provides CRUD operations for annotations (notes, highlights, bookmarks)
and extraction from ebook files.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..db.models import Book, Annotation

logger = logging.getLogger(__name__)


class AnnotationService:
    """Service for managing book annotations."""

    def __init__(self, session: Session, library_path: Optional[Path] = None):
        """
        Initialize the annotation service.

        Args:
            session: SQLAlchemy database session
            library_path: Path to the library root (needed for extraction)
        """
        self.session = session
        self.library_path = Path(library_path) if library_path else None

    def create(
        self,
        book_id: int,
        content: str,
        annotation_type: str = 'note',
        page_number: Optional[int] = None,
        position: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
    ) -> Annotation:
        """
        Create a new annotation for a book.

        Args:
            book_id: Book ID
            content: Annotation text content
            annotation_type: Type (note, highlight, bookmark)
            page_number: Optional page number
            position: Optional position info
            color: Optional color for highlights

        Returns:
            Created Annotation instance
        """
        annotation = Annotation(
            book_id=book_id,
            content=content,
            annotation_type=annotation_type,
            page_number=page_number,
            position=position,
            color=color,
            created_at=datetime.now()
        )
        self.session.add(annotation)
        self.session.commit()

        logger.info(f"Created {annotation_type} annotation for book {book_id}")
        return annotation

    def get(self, annotation_id: int) -> Optional[Annotation]:
        """
        Get an annotation by ID.

        Args:
            annotation_id: Annotation ID

        Returns:
            Annotation instance or None
        """
        return self.session.query(Annotation).filter_by(id=annotation_id).first()

    def list(
        self,
        book_id: int,
        type_filter: Optional[str] = None,
        page_filter: Optional[int] = None,
    ) -> List[Annotation]:
        """
        List annotations for a book.

        Args:
            book_id: Book ID
            type_filter: Optional annotation type filter
            page_filter: Optional page number filter

        Returns:
            List of Annotation instances
        """
        query = self.session.query(Annotation).filter_by(book_id=book_id)

        if type_filter:
            query = query.filter_by(annotation_type=type_filter)

        if page_filter is not None:
            query = query.filter_by(page_number=page_filter)

        return query.order_by(Annotation.page_number.asc().nulls_last(),
                              Annotation.created_at.desc()).all()

    def update(
        self,
        annotation_id: int,
        content: Optional[str] = None,
        page_number: Optional[int] = None,
        color: Optional[str] = None,
    ) -> Optional[Annotation]:
        """
        Update an existing annotation.

        Args:
            annotation_id: Annotation ID
            content: New content (if changing)
            page_number: New page number (if changing)
            color: New color (if changing)

        Returns:
            Updated Annotation or None if not found
        """
        annotation = self.get(annotation_id)
        if not annotation:
            return None

        if content is not None:
            annotation.content = content
        if page_number is not None:
            annotation.page_number = page_number
        if color is not None:
            annotation.color = color

        self.session.commit()
        logger.info(f"Updated annotation {annotation_id}")
        return annotation

    def delete(self, annotation_id: int) -> bool:
        """
        Delete an annotation.

        Args:
            annotation_id: Annotation ID

        Returns:
            True if deleted, False if not found
        """
        annotation = self.get(annotation_id)
        if not annotation:
            return False

        self.session.delete(annotation)
        self.session.commit()
        logger.info(f"Deleted annotation {annotation_id}")
        return True

    def delete_all_for_book(self, book_id: int) -> int:
        """
        Delete all annotations for a book.

        Args:
            book_id: Book ID

        Returns:
            Number of annotations deleted
        """
        count = self.session.query(Annotation).filter_by(book_id=book_id).count()
        self.session.query(Annotation).filter_by(book_id=book_id).delete()
        self.session.commit()
        logger.info(f"Deleted {count} annotations for book {book_id}")
        return count

    def extract_from_file(
        self,
        book_id: int,
        file_format: Optional[str] = None,
    ) -> int:
        """
        Extract annotations from book files and save to database.

        Args:
            book_id: Book ID
            file_format: Optional specific format to extract from

        Returns:
            Number of annotations extracted and saved
        """
        if not self.library_path:
            raise ValueError("library_path required for annotation extraction")

        from .annotation_extraction import AnnotationExtractionService

        book = self.session.query(Book).filter_by(id=book_id).first()
        if not book:
            logger.error(f"Book {book_id} not found")
            return 0

        extraction_service = AnnotationExtractionService(self.library_path)
        total_saved = 0

        for file in book.files:
            # Skip if format filter specified and doesn't match
            if file_format and file.format.lower() != file_format.lower():
                continue

            file_path = self.library_path / file.path
            annotations = extraction_service.extract_annotations(file_path)

            for annot in annotations:
                # Skip duplicates (same content, same page, same type)
                existing = self.session.query(Annotation).filter_by(
                    book_id=book_id,
                    content=annot.content,
                    page_number=annot.page_number,
                    annotation_type=annot.annotation_type
                ).first()

                if existing:
                    continue

                self.create(
                    book_id=book_id,
                    content=annot.content,
                    annotation_type=annot.annotation_type,
                    page_number=annot.page_number,
                    position=annot.position,
                    color=annot.color
                )
                total_saved += 1

        return total_saved

    def export(
        self,
        book_id: int,
        format_type: str = 'json',
        type_filter: Optional[str] = None,
    ) -> str:
        """
        Export annotations for a book in a specific format.

        Args:
            book_id: Book ID
            format_type: Export format (json, markdown, txt)
            type_filter: Optional annotation type filter

        Returns:
            Formatted string of annotations
        """
        annotations = self.list(book_id, type_filter=type_filter)
        book = self.session.query(Book).filter_by(id=book_id).first()

        if format_type == 'json':
            return self._export_json(book, annotations)
        elif format_type == 'markdown':
            return self._export_markdown(book, annotations)
        else:  # txt
            return self._export_txt(book, annotations)

    def _export_json(self, book: Book, annotations: List[Annotation]) -> str:
        """Export annotations as JSON."""
        data = {
            "book_id": book.id if book else None,
            "book_title": book.title if book else "Unknown",
            "exported_at": datetime.now().isoformat(),
            "annotations": [
                {
                    "id": a.id,
                    "type": a.annotation_type,
                    "content": a.content,
                    "page": a.page_number,
                    "color": a.color,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in annotations
            ]
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_markdown(self, book: Book, annotations: List[Annotation]) -> str:
        """Export annotations as Markdown."""
        lines = []
        title = book.title if book else "Unknown Book"
        lines.append(f"# Annotations: {title}\n")
        lines.append(f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        # Group by type
        by_type: Dict[str, List[Annotation]] = {}
        for a in annotations:
            t = a.annotation_type or 'note'
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(a)

        for ann_type, items in by_type.items():
            lines.append(f"\n## {ann_type.title()}s\n")

            for a in items:
                page_info = f" (p. {a.page_number})" if a.page_number else ""
                lines.append(f"- **{page_info}**: {a.content}")

        return "\n".join(lines)

    def _export_txt(self, book: Book, annotations: List[Annotation]) -> str:
        """Export annotations as plain text."""
        lines = []
        title = book.title if book else "Unknown Book"
        lines.append(f"Annotations for: {title}")
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("-" * 40)

        for a in annotations:
            type_info = f"[{a.annotation_type}]" if a.annotation_type else "[note]"
            page_info = f" Page {a.page_number}" if a.page_number else ""
            lines.append(f"\n{type_info}{page_info}")
            lines.append(a.content)

        return "\n".join(lines)

    def count(self, book_id: Optional[int] = None) -> int:
        """
        Count annotations.

        Args:
            book_id: Optional book ID to filter by

        Returns:
            Number of annotations
        """
        query = self.session.query(Annotation)
        if book_id is not None:
            query = query.filter_by(book_id=book_id)
        return query.count()

    def count_by_type(self, book_id: Optional[int] = None) -> Dict[str, int]:
        """
        Count annotations grouped by type.

        Args:
            book_id: Optional book ID to filter by

        Returns:
            Dictionary mapping annotation type to count
        """
        from sqlalchemy import func

        query = self.session.query(
            Annotation.annotation_type,
            func.count(Annotation.id)
        )

        if book_id is not None:
            query = query.filter_by(book_id=book_id)

        query = query.group_by(Annotation.annotation_type)
        result = query.all()

        return {t or 'note': c for t, c in result}

    def to_dict(self, annotation: Annotation) -> Dict[str, Any]:
        """
        Convert an annotation to a dictionary.

        Args:
            annotation: Annotation instance

        Returns:
            Dictionary representation
        """
        return {
            "id": annotation.id,
            "book_id": annotation.book_id,
            "type": annotation.annotation_type,
            "content": annotation.content,
            "page": annotation.page_number,
            "position": annotation.position,
            "color": annotation.color,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
        }
