"""EPUB content extractor (Task 6 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class EpubExtractor:
    version = "epub-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "epub"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("EpubExtractor.extract arrives in Task 6")
