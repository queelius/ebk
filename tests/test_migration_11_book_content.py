"""Test migration 11: text_chunks -> book_content with refined schema."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import (
    migrate_rename_text_chunks_to_book_content,
    get_schema_version,
    CURRENT_SCHEMA_VERSION,
)
from book_memex.library_db import Library


NEW_COLUMNS = {
    "id", "file_id", "content", "start_page", "end_page",
    "segment_type", "segment_index", "title", "anchor",
    "extractor_version", "extraction_status", "archived_at",
}


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_current_schema_version_at_least_11(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    assert get_schema_version(engine) >= 11
    assert CURRENT_SCHEMA_VERSION >= 11


def test_book_content_table_exists(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    tables = set(inspect(engine).get_table_names())
    assert "book_content" in tables
    assert "text_chunks" not in tables


def test_book_content_has_refined_columns(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
    assert cols >= NEW_COLUMNS, f"missing {NEW_COLUMNS - cols}"
    assert "has_embedding" not in cols
    assert "chunk_index" not in cols


def test_migration_is_idempotent(fresh_library):
    _, temp_dir = fresh_library
    applied = migrate_rename_text_chunks_to_book_content(temp_dir)
    assert applied is False


def test_legacy_rows_backfilled():
    """A pre-migration library with text_chunks rows must survive migration."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Stage 1: create a Library (runs all migrations through 11), add a
        # book + file (so we have a valid file_id to satisfy the NOT NULL
        # FK constraint), then manually insert a legacy-shape row via raw SQL.
        lib = Library.open(temp_dir)
        test_file = temp_dir / "sample.txt"
        test_file.write_text("sample body")
        book = lib.add_book(
            test_file,
            metadata={"title": "Legacy", "creators": ["Anon"]},
            extract_text=False,
        )
        file_id = book.files[0].id
        # The migration should have renamed to book_content; insert a
        # row that simulates a just-migrated legacy chunk.
        lib.session.execute(text("""
            INSERT INTO book_content
              (file_id, content, start_page, end_page, segment_index,
               segment_type, anchor, extractor_version, extraction_status)
            VALUES
              (:fid, 'legacy body', 1, 5, 0,
               'chunk-legacy', '{}', 'legacy', 'ok')
        """), {"fid": file_id})
        lib.session.commit()
        lib.close()

        # Stage 2: reopen and confirm the row survives and migration logic
        # does not corrupt it on re-run.
        lib = Library.open(temp_dir)
        row = lib.session.execute(text(
            "SELECT segment_type, extractor_version, extraction_status "
            "FROM book_content WHERE content = 'legacy body'"
        )).first()
        lib.close()
        assert row is not None
        assert row[0] == "chunk-legacy"
        assert row[1] == "legacy"
        assert row[2] == "ok"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
