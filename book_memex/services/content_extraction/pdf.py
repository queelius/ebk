"""PDF content extractor.

One Segment per page. Anchor is {"page": <1-based>}. Pages with empty or
near-empty text (< 5 non-whitespace chars) are flagged
extraction_status="no_text_layer" so downstream consumers can surface
the fact instead of silently indexing nothing.
"""

from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

from . import Segment


_MIN_PAGE_TEXT_CHARS = 5


class PdfExtractor:
    version = "pdf-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "pdf"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        reader = PdfReader(str(file_path))
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            stripped = text.strip()
            status = "ok" if len(stripped) >= _MIN_PAGE_TEXT_CHARS else "no_text_layer"
            yield Segment(
                segment_type="page",
                segment_index=i,
                title=None,
                anchor={"page": i + 1},  # 1-based
                text=stripped if status == "ok" else "",
                start_page=i + 1,
                end_page=i + 1,
                extraction_status=status,
            )
