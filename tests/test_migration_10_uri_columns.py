"""Test migration 10: uuid + color + anchors + progress_anchor."""
import tempfile
import shutil
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from book_memex.db.models import Base, Book, Marginalia, ReadingSession, PersonalMetadata
from book_memex.library_db import Library


UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_marginalia_has_uuid_color_archived_at(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("marginalia")}
    assert {"uuid", "color", "archived_at"}.issubset(cols)


def test_reading_sessions_has_uuid_anchors(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("reading_sessions")}
    assert {"uuid", "start_anchor", "end_anchor", "archived_at"}.issubset(cols)


def test_personal_metadata_has_progress_anchor(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("personal_metadata")}
    assert "progress_anchor" in cols


def test_marginalia_uuid_unique_index(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    with engine.begin() as conn:
        # Attempting two rows with the same UUID should fail.
        conn.execute(text("""
            INSERT INTO marginalia (uuid, content, created_at, updated_at)
            VALUES ('dup', 'a', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        with pytest.raises(Exception):
            conn.execute(text("""
                INSERT INTO marginalia (uuid, content, created_at, updated_at)
                VALUES ('dup', 'b', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))


def test_existing_marginalia_rows_get_uuid_backfill():
    """Simulate: a pre-migration library with marginalia rows. After migration, each has a UUID."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Stage 1: build a pre-migration-10 marginalia table by hand. We
        # bypass the ORM (which now declares uuid NOT NULL on fresh tables)
        # and create a legacy schema directly with raw SQL, mirroring what
        # an older library on disk would look like.
        db_path = temp_dir / "library.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE marginalia (
                    id INTEGER NOT NULL PRIMARY KEY,
                    content TEXT,
                    highlighted_text TEXT,
                    page_number INTEGER,
                    position JSON,
                    category VARCHAR(100),
                    pinned BOOLEAN DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME
                )
            """))
            conn.execute(text("""
                CREATE TABLE reading_sessions (
                    id INTEGER NOT NULL PRIMARY KEY,
                    book_id INTEGER NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    pages_read INTEGER DEFAULT 0,
                    comprehension_score FLOAT
                )
            """))
            conn.execute(text("""
                CREATE TABLE personal_metadata (
                    id INTEGER NOT NULL PRIMARY KEY,
                    book_id INTEGER NOT NULL,
                    rating FLOAT
                )
            """))
            conn.execute(text(
                "INSERT INTO marginalia (content, created_at, updated_at) "
                "VALUES ('x', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            mid = conn.execute(text("SELECT last_insert_rowid()")).scalar()
        engine.dispose()

        # Stage 2: run the migration (should add uuid column and backfill it)
        from book_memex.db.migrations import migrate_add_uri_columns
        migrate_add_uri_columns(temp_dir)

        # Stage 3: verify the legacy row got a backfilled uuid
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            row = conn.execute(text(
                f"SELECT uuid FROM marginalia WHERE id = {mid}"
            )).scalar()
        engine.dispose()
        assert row is not None
        assert UUID_HEX_RE.match(row), f"expected 32-hex UUID, got {row!r}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
