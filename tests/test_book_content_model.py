"""Test BookContent ORM model (renamed from TextChunk with refined schema)."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import Book, File, BookContent, TextChunk


@pytest.fixture
def temp_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_book_content_is_sqlalchemy_class(temp_library):
    """BookContent should be usable as a normal ORM class."""
    # Create a parent book and file so the FK constraint is satisfied.
    book = Book(title="Test Book", unique_id="abc123")
    temp_library.session.add(book)
    temp_library.session.flush()

    f = File(book_id=book.id, path="test.epub", format="epub", file_hash="deadbeef")
    temp_library.session.add(f)
    temp_library.session.flush()

    bc = BookContent(
        file_id=f.id,
        content="hello world",
        segment_type="chapter",
        segment_index=0,
        title="Chapter 1",
        anchor={"cfi": "epubcfi(/6/2[chap01]!/4)"},
        extractor_version="epub-v1",
        extraction_status="ok",
    )
    temp_library.session.add(bc)
    temp_library.session.commit()

    fetched = temp_library.session.get(BookContent, bc.id)
    assert fetched.content == "hello world"
    assert fetched.segment_type == "chapter"
    assert fetched.segment_index == 0
    assert fetched.title == "Chapter 1"
    assert fetched.anchor == {"cfi": "epubcfi(/6/2[chap01]!/4)"}
    assert fetched.extractor_version == "epub-v1"
    assert fetched.extraction_status == "ok"
    assert fetched.archived_at is None


def test_text_chunk_alias_points_to_book_content():
    """Legacy imports of TextChunk must still resolve to the same class."""
    assert TextChunk is BookContent


def test_no_has_embedding_attribute(temp_library):
    """The has_embedding column was dropped."""
    assert not hasattr(BookContent, "has_embedding")
