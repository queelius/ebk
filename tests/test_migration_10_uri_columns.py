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
        # Stage 1: create a library and a Marginalia row via the ORM
        lib = Library.open(temp_dir)
        # Create via raw SQL to simulate a pre-migration-10 row (no uuid).
        # But since migrations run at open(), the row we insert now will have uuid.
        # Instead, null-out the uuid to simulate legacy state, then re-run migration.
        with lib.session.begin():
            lib.session.execute(text(
                "INSERT INTO marginalia (content, created_at, updated_at) VALUES ('x', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            mid = lib.session.execute(text("SELECT last_insert_rowid()")).scalar()
            lib.session.execute(text("UPDATE marginalia SET uuid = NULL WHERE id = :i"), {"i": mid})
        lib.close()

        # Stage 2: re-run migration (should backfill)
        from book_memex.db.migrations import migrate_add_uri_columns
        migrate_add_uri_columns(temp_dir)

        # Stage 3: verify
        lib = Library.open(temp_dir)
        row = lib.session.execute(text(
            f"SELECT uuid FROM marginalia WHERE id = {mid}"
        )).scalar()
        lib.close()
        assert row is not None
        assert UUID_HEX_RE.match(row), f"expected 32-hex UUID, got {row!r}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
