"""TXT content extractor (Task 8 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class TxtExtractor:
    version = "txt-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() in ("txt", "md")

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("TxtExtractor.extract arrives in Task 8")
