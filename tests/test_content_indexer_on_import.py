"""Verify that importing a book triggers content indexing."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import BookContent


@pytest.fixture
def tmp_lib():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_importing_epub_writes_book_content(tmp_lib, sample_epub):
    dest = tmp_lib.library_path / "imported.epub"
    shutil.copy(sample_epub, dest)
    book = tmp_lib.add_book(
        dest,
        metadata={"title": "Imported", "creators": ["A"]},
        extract_text=True,  # new extract_text path now runs content indexer too
    )

    rows = (
        tmp_lib.session.query(BookContent)
        .filter(BookContent.file_id == book.primary_file.id)
        .all()
    )
    assert len(rows) == 3
    assert all(r.extractor_version == "epub-v1" for r in rows)


def test_importing_unsupported_format_still_succeeds(tmp_lib, tmp_path):
    """A format with no extractor imports normally; just no BookContent rows."""
    unknown = tmp_lib.library_path / "mystery.xyz"
    unknown.write_bytes(b"not a known format")
    book = tmp_lib.add_book(
        unknown,
        metadata={"title": "Mystery", "creators": ["B"]},
        extract_text=True,
    )
    # Import succeeded; no content rows.
    rows = (
        tmp_lib.session.query(BookContent)
        .filter(BookContent.file_id == book.primary_file.id)
        .all()
    )
    assert rows == []
