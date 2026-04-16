"""TXT/MD content extractor.

Emits exactly one Segment containing the entire file. Encoding is
utf-8 with "replace" errors so malformed bytes do not halt extraction.
Anchor is {"offset": 0, "length": <byte count>}.
"""

from pathlib import Path
from typing import Iterator

from . import Segment


class TxtExtractor:
    version = "txt-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() in ("txt", "md")

    def extract(self, file_path: Path) -> Iterator[Segment]:
        data = file_path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        yield Segment(
            segment_type="text",
            segment_index=0,
            title=None,
            anchor={"offset": 0, "length": len(data)},
            text=text,
            extraction_status="ok",
        )
