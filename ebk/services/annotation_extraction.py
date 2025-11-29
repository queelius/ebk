"""
Annotation extraction service for ebook files.

Extracts highlights, notes, and bookmarks from PDF and EPUB files.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedAnnotation:
    """Represents an extracted annotation."""
    annotation_type: str  # 'highlight', 'note', 'bookmark', 'underline', 'strikeout'
    content: str  # The highlighted/noted text or note content
    page_number: Optional[int] = None
    color: Optional[str] = None
    position: Optional[Dict[str, Any]] = None  # Position info
    note: Optional[str] = None  # Additional note attached to highlight


class AnnotationExtractionService:
    """Service for extracting annotations from ebook files."""

    def __init__(self, library_root: Path):
        self.library_root = Path(library_root)

    def extract_annotations(self, file_path: Path) -> List[ExtractedAnnotation]:
        """
        Extract all annotations from an ebook file.

        Args:
            file_path: Path to the ebook file

        Returns:
            List of extracted annotations
        """
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self._extract_pdf_annotations(file_path)
        elif suffix == '.epub':
            return self._extract_epub_annotations(file_path)
        else:
            logger.warning(f"Unsupported format for annotation extraction: {suffix}")
            return []

    def _extract_pdf_annotations(self, file_path: Path) -> List[ExtractedAnnotation]:
        """Extract annotations from a PDF file using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Install with: pip install pymupdf")
            return []

        annotations = []

        try:
            doc = fitz.open(file_path)

            for page_num, page in enumerate(doc, start=1):
                # Get all annotations on this page
                for annot in page.annots() or []:
                    annot_type = annot.type[1]  # e.g., 'Highlight', 'Text', 'StrikeOut'

                    # Map PDF annotation types to our types
                    type_mapping = {
                        'Highlight': 'highlight',
                        'Underline': 'underline',
                        'StrikeOut': 'strikeout',
                        'Squiggly': 'underline',
                        'Text': 'note',  # Sticky note
                        'FreeText': 'note',
                        'Ink': 'drawing',
                    }

                    our_type = type_mapping.get(annot_type, 'other')
                    if our_type == 'other':
                        continue  # Skip unsupported types

                    # Get the highlighted/annotated text
                    content = ""
                    note_content = None

                    # For text markup annotations (highlight, underline, etc.)
                    if annot_type in ['Highlight', 'Underline', 'StrikeOut', 'Squiggly']:
                        # Get the text under the annotation
                        try:
                            quads = annot.vertices
                            if quads:
                                # Extract text from the annotation area
                                rect = annot.rect
                                content = page.get_text("text", clip=rect).strip()
                        except Exception:
                            pass

                        # Check for popup note attached to highlight
                        info = annot.info
                        if info.get('content'):
                            note_content = info['content']

                    # For text notes (sticky notes)
                    elif annot_type in ['Text', 'FreeText']:
                        info = annot.info
                        content = info.get('content', '') or annot.get_text() or ''

                    if not content and not note_content:
                        continue

                    # Get color
                    color = None
                    colors = annot.colors
                    if colors and colors.get('stroke'):
                        # Convert RGB to hex
                        rgb = colors['stroke']
                        if len(rgb) >= 3:
                            color = '#{:02x}{:02x}{:02x}'.format(
                                int(rgb[0] * 255),
                                int(rgb[1] * 255),
                                int(rgb[2] * 255)
                            )

                    # Get position
                    rect = annot.rect
                    position = {
                        'x': rect.x0,
                        'y': rect.y0,
                        'width': rect.width,
                        'height': rect.height
                    }

                    annotations.append(ExtractedAnnotation(
                        annotation_type=our_type,
                        content=content or note_content or "",
                        page_number=page_num,
                        color=color,
                        position=position,
                        note=note_content if content else None
                    ))

            doc.close()
            logger.info(f"Extracted {len(annotations)} annotations from PDF: {file_path.name}")

        except Exception as e:
            logger.error(f"Error extracting PDF annotations: {e}")

        return annotations

    def _extract_epub_annotations(self, file_path: Path) -> List[ExtractedAnnotation]:
        """
        Extract annotations from an EPUB file.

        Note: EPUB files don't have a standard annotation format.
        This looks for common annotation storage patterns used by some readers.
        """
        try:
            from ebooklib import epub
        except ImportError:
            logger.error("ebooklib not installed. Install with: pip install ebooklib")
            return []

        annotations = []

        try:
            book = epub.read_epub(file_path)

            # Look for annotation files that some readers create
            # Common patterns: META-INF/annotations.xml, OPS/annotations.xml
            for item in book.get_items():
                name = item.get_name().lower()

                # Check for annotation files
                if 'annotation' in name and name.endswith('.xml'):
                    content = item.get_content().decode('utf-8', errors='ignore')
                    annotations.extend(self._parse_epub_annotations_xml(content))

                # Check for Open Annotation format
                elif name.endswith('.json') and 'annotation' in name:
                    import json
                    try:
                        content = item.get_content().decode('utf-8', errors='ignore')
                        data = json.loads(content)
                        annotations.extend(self._parse_open_annotation_json(data))
                    except json.JSONDecodeError:
                        pass

            logger.info(f"Extracted {len(annotations)} annotations from EPUB: {file_path.name}")

        except Exception as e:
            logger.error(f"Error extracting EPUB annotations: {e}")

        return annotations

    def _parse_epub_annotations_xml(self, xml_content: str) -> List[ExtractedAnnotation]:
        """Parse common EPUB annotation XML formats."""
        annotations = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(xml_content, 'xml')

            # Try various common annotation formats
            # Adobe Digital Editions format
            for annot in soup.find_all(['annotation', 'highlight', 'note']):
                content = annot.get_text(strip=True)
                if content:
                    annot_type = annot.name
                    if annot_type == 'annotation':
                        annot_type = 'note'

                    annotations.append(ExtractedAnnotation(
                        annotation_type=annot_type,
                        content=content,
                        page_number=None,
                        color=annot.get('color')
                    ))

        except Exception as e:
            logger.debug(f"Error parsing EPUB annotations XML: {e}")

        return annotations

    def _parse_open_annotation_json(self, data: Any) -> List[ExtractedAnnotation]:
        """Parse Open Annotation (W3C Web Annotation) format."""
        annotations = []

        try:
            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue

                # W3C Web Annotation format
                body = item.get('body', {})
                target = item.get('target', {})

                content = ""
                if isinstance(body, str):
                    content = body
                elif isinstance(body, dict):
                    content = body.get('value', '') or body.get('text', '')

                if not content:
                    continue

                # Determine type from motivation
                motivation = item.get('motivation', 'highlighting')
                type_mapping = {
                    'highlighting': 'highlight',
                    'commenting': 'note',
                    'bookmarking': 'bookmark',
                    'describing': 'note',
                }
                annot_type = type_mapping.get(motivation, 'note')

                annotations.append(ExtractedAnnotation(
                    annotation_type=annot_type,
                    content=content,
                    page_number=None
                ))

        except Exception as e:
            logger.debug(f"Error parsing Open Annotation JSON: {e}")

        return annotations


def extract_and_save_annotations(
    library,
    book_id: int,
    file_format: Optional[str] = None
) -> int:
    """
    Extract annotations from a book's files and save to database.

    Args:
        library: Library instance
        book_id: Book ID to extract annotations for
        file_format: Optional specific format to extract from (e.g., 'pdf')

    Returns:
        Number of annotations extracted and saved
    """
    book = library.get_book(book_id)
    if not book:
        logger.error(f"Book {book_id} not found")
        return 0

    service = AnnotationExtractionService(library.library_path)
    total_saved = 0

    for file in book.files:
        # Skip if format filter specified and doesn't match
        if file_format and file.format.lower() != file_format.lower():
            continue

        file_path = library.library_path / file.path
        annotations = service.extract_annotations(file_path)

        for annot in annotations:
            # Skip duplicates (same content, same page, same type)
            existing = [a for a in book.annotations
                       if a.content == annot.content
                       and a.page_number == annot.page_number
                       and a.annotation_type == annot.annotation_type]
            if existing:
                continue

            library.add_annotation(
                book_id=book_id,
                content=annot.content,
                annotation_type=annot.annotation_type,
                page_number=annot.page_number,
                position=annot.position,
                color=annot.color
            )
            total_saved += 1

    return total_saved
