"""Content indexer: run an extractor over a File and write BookContent rows.

Atomic per-file reindex: old rows for the file are deleted before new rows
are inserted. FTS triggers keep book_content_fts in sync automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from book_memex.db.models import BookContent, File
from book_memex.services.content_extraction import (
    Segment, get_extractor,
)


logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    file_id: Optional[int]
    status: str  # "ok" | "unsupported_format" | "extractor_error" | "no_text_layer"
    segments_written: int
    extractor_version: Optional[str]
    detail: Optional[str] = None


class ContentIndexer:
    """Extract + persist book segments for a File row."""

    def __init__(self, session: Session, library_path: Optional[Path] = None):
        self.session = session
        self.library_path = library_path

    def index_file(self, file_row: File) -> IndexResult:
        """Extract content from `file_row` and write BookContent rows.

        Deletes any existing BookContent rows for the file first.
        Returns an IndexResult summarizing the outcome.
        """
        try:
            extractor = get_extractor(file_row.format)
        except ValueError as exc:
            logger.info(
                "skip unsupported format %r for file_id=%s: %s",
                file_row.format, file_row.id, exc,
            )
            return IndexResult(
                file_id=file_row.id,
                status="unsupported_format",
                segments_written=0,
                extractor_version=None,
                detail=str(exc),
            )

        file_path = self._resolve_path(file_row)

        # Clear existing rows for this file (idempotent reindex).
        self.session.query(BookContent).filter(
            BookContent.file_id == file_row.id
        ).delete(synchronize_session=False)
        self.session.flush()

        segments_written = 0
        statuses: set[str] = set()
        try:
            for seg in extractor.extract(file_path):
                row = BookContent(
                    file_id=file_row.id,
                    content=seg.text,
                    segment_type=seg.segment_type,
                    segment_index=seg.segment_index,
                    title=seg.title,
                    anchor=seg.anchor,
                    start_page=seg.start_page,
                    end_page=seg.end_page,
                    extractor_version=extractor.version,
                    extraction_status=seg.extraction_status,
                )
                self.session.add(row)
                segments_written += 1
                statuses.add(seg.extraction_status)
        except Exception as exc:
            logger.exception("extractor error for file_id=%s", file_row.id)
            self.session.rollback()
            return IndexResult(
                file_id=file_row.id,
                status="extractor_error",
                segments_written=0,
                extractor_version=extractor.version,
                detail=str(exc),
            )

        self.session.commit()

        # Aggregate status: if any segment was ok, treat result as ok; if all
        # segments were no_text_layer, escalate that to the result.
        if "ok" in statuses:
            status = "ok"
        elif statuses == {"no_text_layer"}:
            status = "no_text_layer"
        else:
            status = "ok" if segments_written else "extractor_error"

        return IndexResult(
            file_id=file_row.id,
            status=status,
            segments_written=segments_written,
            extractor_version=extractor.version,
        )

    def _resolve_path(self, file_row: File) -> Path:
        """Absolute path to the file on disk."""
        rel = Path(file_row.path)
        if rel.is_absolute():
            return rel
        if self.library_path is None:
            return rel
        return self.library_path / rel
