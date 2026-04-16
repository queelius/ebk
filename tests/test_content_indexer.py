"""Tests for ContentIndexer: run extractor and write BookContent rows."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import BookContent, File
from book_memex.services.content_indexer import ContentIndexer, IndexResult


@pytest.fixture
def lib_with_epub(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    # Copy EPUB into the library and import via add_book.
    dest = lib.library_path / "sample.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(
        dest,
        metadata={"title": "Phase 2 Sample", "creators": ["Test Author"]},
        extract_text=False,  # we drive extraction manually below
    )
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_index_file_writes_segments(lib_with_epub):
    lib, book = lib_with_epub
    file_row = book.primary_file
    assert file_row is not None

    indexer = ContentIndexer(lib.session, lib.library_path)
    result = indexer.index_file(file_row)

    assert isinstance(result, IndexResult)
    assert result.segments_written == 3
    assert result.status == "ok"
    assert result.extractor_version == "epub-v1"

    rows = (
        lib.session.query(BookContent)
        .filter(BookContent.file_id == file_row.id)
        .order_by(BookContent.segment_index)
        .all()
    )
    assert len(rows) == 3
    assert all(r.segment_type == "chapter" for r in rows)


def test_reindex_replaces_prior_rows(lib_with_epub):
    lib, book = lib_with_epub
    file_row = book.primary_file
    indexer = ContentIndexer(lib.session, lib.library_path)

    indexer.index_file(file_row)
    first_ids = {
        r.id for r in lib.session.query(BookContent)
                                  .filter(BookContent.file_id == file_row.id).all()
    }
    assert len(first_ids) == 3

    # Reindex: old rows should be replaced, not accumulated.
    indexer.index_file(file_row)
    second_rows = (
        lib.session.query(BookContent)
        .filter(BookContent.file_id == file_row.id)
        .all()
    )
    assert len(second_rows) == 3, "reindex should replace rows, not accumulate"

    # Verify content is fresh (same extractor version, correct segment types).
    assert all(r.extractor_version == "epub-v1" for r in second_rows)
    assert all(r.segment_type == "chapter" for r in second_rows)


def test_index_unsupported_format_records_failure(lib_with_epub):
    lib, book = lib_with_epub
    # Fabricate a File with an unsupported format for negative-path testing.
    bogus_file = File(
        book_id=book.id,
        path="bogus.xyz",
        format="xyz",
        file_hash="0" * 64,
        size_bytes=0,
    )
    lib.session.add(bogus_file)
    lib.session.commit()

    indexer = ContentIndexer(lib.session, lib.library_path)
    result = indexer.index_file(bogus_file)

    assert result.status == "unsupported_format"
    assert result.segments_written == 0
