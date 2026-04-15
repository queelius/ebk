"""Test migration 9: add archived_at to existing tables."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import (
    migrate_add_archived_at,
    get_schema_version,
    CURRENT_SCHEMA_VERSION,
)
from book_memex.library_db import Library


SOFT_DELETE_TABLES = [
    "books", "authors", "subjects", "tags",
    "files", "covers", "personal_metadata",
    "marginalia", "reading_sessions",
]


@pytest.fixture
def fresh_library():
    """A freshly initialized library (already at latest schema)."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_current_schema_version_is_9_or_later(fresh_library):
    lib, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    assert get_schema_version(engine) >= 9
    assert CURRENT_SCHEMA_VERSION >= 9


def test_every_soft_delete_table_has_archived_at(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table)}
        assert "archived_at" in cols, f"{table} is missing archived_at column"


def test_archived_at_is_nullable(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert cols["archived_at"]["nullable"] is True, \
            f"{table}.archived_at should be nullable"


def test_migration_is_idempotent(fresh_library):
    """Running the migration twice returns False (already applied)."""
    _, temp_dir = fresh_library
    # Library.open() already ran migrations; second invocation must be a no-op.
    applied = migrate_add_archived_at(temp_dir)
    assert applied is False
