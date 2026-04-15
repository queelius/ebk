"""Tests for ReadingSessionService."""
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from book_memex.library_db import Library
from book_memex.services.reading_session_service import ReadingSessionService


@pytest.fixture
def lib_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_start_session(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id, start_anchor={"cfi": "epubcfi(/6/4!/4)"})
    assert rs.uuid is not None
    assert rs.start_anchor == {"cfi": "epubcfi(/6/4!/4)"}
    assert rs.end_time is None


def test_end_session(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    ended = svc.end(rs.uuid, end_anchor={"cfi": "epubcfi(/6/4!/8)"})
    assert ended.end_time is not None
    assert ended.end_anchor == {"cfi": "epubcfi(/6/4!/8)"}


def test_end_idempotent_on_already_ended(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    svc.end(rs.uuid)
    # Ending again should either return the already-ended session
    # or raise a clear error. Spec: idempotent.
    again = svc.end(rs.uuid)
    assert again.uuid == rs.uuid


def test_list_for_book_filters_archived(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs1 = svc.start(book_id=book.id)
    rs2 = svc.start(book_id=book.id)
    svc.archive(rs2)

    active = svc.list_for_book(book.id)
    assert rs1.uuid in {r.uuid for r in active}
    assert rs2.uuid not in {r.uuid for r in active}


def test_archive_restore(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    svc.archive(rs)
    assert rs.archived_at is not None
    svc.restore(rs)
    assert rs.archived_at is None
