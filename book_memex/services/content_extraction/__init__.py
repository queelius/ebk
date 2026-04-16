"""Content extraction for book files.

Each format-specific extractor implements the Extractor Protocol, yielding
Segment records. The dispatch helper get_extractor(format) returns the
right instance. Versioning lets book-memex reindex specific books when an
extractor improves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, Optional, Protocol, runtime_checkable


@dataclass
class Segment:
    """One extracted piece of a book file.

    segment_type:
        "chapter" for EPUBs (one per spine item),
        "page" for PDFs (one per page),
        "text" for whole-file TXT/MD.
    segment_index:
        Stable index within the book. Combined with segment_type, forms
        a durable intra-book identifier.
    anchor:
        Content-intrinsic position pointer, JSON-safe.
        EPUB: {"cfi": "epubcfi(...)"}, PDF: {"page": <1-based>},
        TXT: {"offset": 0, "length": <n>}.
    extraction_status:
        "ok" for normal segments; "no_text_layer" for scanned PDFs;
        "partial" for segments where extraction succeeded but may be
        incomplete (e.g., DRM-protected chunks).
    """
    segment_type: str
    segment_index: int
    title: Optional[str]
    anchor: Dict
    text: str
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    extraction_status: str = "ok"


@runtime_checkable
class Extractor(Protocol):
    """Format-specific content extractor."""

    version: str  # e.g., "epub-v1", "pdf-v1", "txt-v1"

    def supports(self, book_format: str) -> bool: ...

    def extract(self, file_path: Path) -> Iterator[Segment]: ...


_REGISTRY: Dict[str, Extractor] = {}
SUPPORTED_FORMATS = ("epub", "pdf", "txt")


def register(fmt: str, extractor: Extractor) -> None:
    """Register an extractor for a file format. Later registrations override."""
    _REGISTRY[fmt.lower()] = extractor


def get_extractor(book_format: str) -> Extractor:
    """Return the registered extractor for a format. Raises ValueError if unknown."""
    ex = _REGISTRY.get(book_format.lower())
    if ex is None:
        raise ValueError(f"no extractor registered for format {book_format!r}")
    return ex


# Lazy registration: extractors self-register on import.
def _install_default_extractors() -> None:
    from book_memex.services.content_extraction.epub import EpubExtractor
    from book_memex.services.content_extraction.pdf import PdfExtractor
    from book_memex.services.content_extraction.txt import TxtExtractor
    register("epub", EpubExtractor())
    register("pdf", PdfExtractor())
    register("txt", TxtExtractor())


_install_default_extractors()
