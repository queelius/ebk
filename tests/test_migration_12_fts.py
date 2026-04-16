"""Test migration 12: book_content_fts virtual table + triggers."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import CURRENT_SCHEMA_VERSION
from book_memex.db.models import Book, File, BookContent
from book_memex.library_db import Library


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def lib_with_file(fresh_library):
    """Return (lib, file) with a Book+File already created for FK satisfaction."""
    lib, _ = fresh_library
    book = Book(title="FTS Test Book", unique_id="fts-test-001")
    lib.session.add(book)
    lib.session.flush()
    f = File(book_id=book.id, path="test.epub", format="epub", file_hash="ftsdeadbeef")
    lib.session.add(f)
    lib.session.flush()
    return lib, f


def test_schema_version_at_least_12(fresh_library):
    assert CURRENT_SCHEMA_VERSION >= 12


def test_book_content_fts_exists(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    tables = set(inspect(engine).get_table_names())
    assert "book_content_fts" in tables


def test_insert_syncs_to_fts(lib_with_file):
    lib, f = lib_with_file
    bc = BookContent(
        file_id=f.id, content="the quick brown fox",
        segment_type="chapter", segment_index=0, title="Intro",
        anchor={}, extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()

    # Query FTS directly.
    rows = lib.session.execute(text(
        "SELECT rowid FROM book_content_fts WHERE book_content_fts MATCH 'quick fox'"
    )).fetchall()
    assert any(r[0] == bc.id for r in rows)


def test_update_syncs_to_fts(lib_with_file):
    lib, f = lib_with_file
    bc = BookContent(
        file_id=f.id, content="apple",
        segment_type="chapter", segment_index=0, anchor={},
        extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()

    bc.content = "banana"
    lib.session.commit()

    apple_hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'apple'"
    )).scalar()
    banana_hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'banana'"
    )).scalar()
    assert apple_hits == 0
    assert banana_hits == 1


def test_delete_syncs_to_fts(lib_with_file):
    lib, f = lib_with_file
    bc = BookContent(
        file_id=f.id, content="ephemeral",
        segment_type="chapter", segment_index=0, anchor={},
        extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()
    lib.session.delete(bc)
    lib.session.commit()

    hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'ephemeral'"
    )).scalar()
    assert hits == 0
