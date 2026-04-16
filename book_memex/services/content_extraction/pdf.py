"""PDF content extractor (Task 7 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class PdfExtractor:
    version = "pdf-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "pdf"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("PdfExtractor.extract arrives in Task 7")
