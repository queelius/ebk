"""EPUB content extractor.

Walks the EPUB spine, emitting one Segment per document item (skipping
the nav). Title is extracted from the first <h1> when present, falling
back to the spine item's TOC title. Anchor is a chapter-root CFI derived
from the spine position (even-index pattern: item N occupies CFI /6/<2N>).
"""

from pathlib import Path
from typing import Iterator, Optional

from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT

from . import Segment


class EpubExtractor:
    version = "epub-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "epub"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        book = epub.read_epub(str(file_path))

        # Walk the spine in order. `book.spine` is a list of (item_id, linear)
        # tuples. The nav item is typically first and is not content; skip it
        # for text extraction BUT use the real spine position for CFI so
        # anchors resolve in EPUB.js (which indexes the full spine).
        segments_yielded = 0
        for spine_position, spine_entry in enumerate(book.spine):
            item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
            item = book.get_item_with_id(item_id)
            if item is None:
                continue
            if item.get_type() != ITEM_DOCUMENT:
                continue
            # Heuristic: skip common nav filename patterns.
            href = (item.get_name() or "").lower()
            if "nav" in href or href.endswith(("toc.xhtml", "toc.html")):
                continue

            raw = item.get_body_content() or item.get_content()
            soup = BeautifulSoup(raw, "html.parser")

            # Title: first <h1>, else <title>, else the item's own attribute.
            title = None
            h1 = soup.find("h1")
            if h1 is not None and h1.get_text(strip=True):
                title = h1.get_text(strip=True)
            else:
                title_tag = soup.find("title")
                if title_tag is not None and title_tag.get_text(strip=True):
                    title = title_tag.get_text(strip=True)
            if not title:
                title = getattr(item, "title", None) or None

            text = _clean_text(soup.get_text(separator=" ", strip=True))

            # CFI spine position uses /6/<2*(spine_position+1)>. We use the
            # raw spine position (including nav), NOT the filtered segment
            # index, because EPUB.js resolves CFIs against the full spine.
            cfi = f"epubcfi(/6/{(spine_position + 1) * 2}[{item.get_id()}]!/4)"

            yield Segment(
                segment_type="chapter",
                segment_index=segments_yielded,
                title=title,
                anchor={"cfi": cfi},
                text=text,
                extraction_status="ok",
            )
            segments_yielded += 1


def _clean_text(text: str) -> str:
    """Collapse runs of whitespace; trim ends."""
    return " ".join(text.split())
