"""Tests for `book-memex extract` and `book-memex reindex-content` CLI."""
import tempfile
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def tmp_lib_with_book(sample_epub):
    from book_memex.library_db import Library

    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "a.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(dest, metadata={"title": "A", "creators": ["X"]}, extract_text=False)
    lib.close()
    yield temp_dir, book.id
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_extract_single_book(tmp_lib_with_book):
    from book_memex.cli import app

    temp_dir, book_id = tmp_lib_with_book
    runner = CliRunner()
    result = runner.invoke(
        app, ["extract", str(book_id), "--library-path", str(temp_dir)]
    )
    assert result.exit_code == 0
    assert "segments_written" in result.output
    assert "3" in result.output  # 3 chapters in the sample EPUB
