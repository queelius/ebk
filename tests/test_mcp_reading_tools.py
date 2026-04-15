"""Tests for MCP reading-state tool implementations."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    start_reading_session_impl, end_reading_session_impl,
    list_reading_sessions_impl, delete_reading_session_impl,
    restore_reading_session_impl,
    get_reading_progress_impl, set_reading_progress_impl,
)


@pytest.fixture
def lib_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_start_and_end_session(lib_and_book):
    lib, book = lib_and_book
    started = start_reading_session_impl(
        lib.session, book_id=book.id, start_anchor={"cfi": "X"}
    )
    assert started["uri"].startswith("book-memex://reading/")
    ended = end_reading_session_impl(
        lib.session, uuid=started["uuid"], end_anchor={"cfi": "Y"}
    )
    assert ended["end_time"] is not None


def test_list_reading_sessions(lib_and_book):
    lib, book = lib_and_book
    start_reading_session_impl(lib.session, book_id=book.id)
    start_reading_session_impl(lib.session, book_id=book.id)
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert len(rows) == 2


def test_soft_delete_and_restore_session(lib_and_book):
    lib, book = lib_and_book
    s = start_reading_session_impl(lib.session, book_id=book.id)
    delete_reading_session_impl(lib.session, uuid=s["uuid"])
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert s["uuid"] not in {r["uuid"] for r in rows}
    restore_reading_session_impl(lib.session, uuid=s["uuid"])
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert s["uuid"] in {r["uuid"] for r in rows}


def test_progress_get_and_set(lib_and_book):
    lib, book = lib_and_book
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["anchor"] is None

    set_reading_progress_impl(
        lib.session, book_id=book.id,
        anchor={"cfi": "Z"}, percentage=30, force=False,
    )
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["anchor"] == {"cfi": "Z"}
    assert p["percentage"] == 30


def test_progress_rejects_backward(lib_and_book):
    lib, book = lib_and_book
    set_reading_progress_impl(
        lib.session, book_id=book.id, anchor={"cfi": "A"}, percentage=50, force=False
    )
    with pytest.raises(ValueError):
        set_reading_progress_impl(
            lib.session, book_id=book.id, anchor={"cfi": "B"}, percentage=20, force=False
        )

    # force=True bypasses the check.
    set_reading_progress_impl(
        lib.session, book_id=book.id, anchor={"cfi": "B"}, percentage=20, force=True
    )
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["percentage"] == 20


def test_reading_session_impls_accept_uris(lib_and_book):
    """end/delete/restore should accept either a bare uuid or a full URI."""
    lib, book = lib_and_book
    started = start_reading_session_impl(lib.session, book_id=book.id)
    uri = started["uri"]

    # end by URI
    ended = end_reading_session_impl(lib.session, uuid=uri)
    assert ended["end_time"] is not None

    # soft-delete by URI
    delete_reading_session_impl(lib.session, uuid=uri)
    # restore by URI
    restored = restore_reading_session_impl(lib.session, uuid=uri)
    assert restored["archived_at"] is None

    # hard-delete by URI
    delete_reading_session_impl(lib.session, uuid=uri, hard=True)


def test_reading_session_impls_reject_wrong_kind_uri(lib_and_book):
    """Passing a book URI where a reading URI is expected raises ValueError."""
    lib, book = lib_and_book
    with pytest.raises(ValueError):
        end_reading_session_impl(lib.session, uuid=book.uri)
    with pytest.raises(ValueError):
        delete_reading_session_impl(lib.session, uuid=book.uri)
