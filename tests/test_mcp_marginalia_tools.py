"""Tests for MCP marginalia tool implementations."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    list_marginalia_impl, get_marginalia_impl, add_marginalia_impl,
    update_marginalia_impl, delete_marginalia_impl, restore_marginalia_impl,
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


def test_add_marginalia_by_uri(lib_and_book):
    lib, book = lib_and_book
    result = add_marginalia_impl(
        lib.session,
        book_uris=[book.uri],
        content="note",
        highlighted_text="passage",
        page_number=5,
        color="#ffff00",
    )
    assert result["uri"].startswith("book-memex://marginalia/")
    assert result["scope"] == "highlight"


def test_list_marginalia(lib_and_book):
    lib, book = lib_and_book
    add_marginalia_impl(lib.session, book_uris=[book.uri], content="a")
    add_marginalia_impl(lib.session, book_uris=[book.uri], content="b")
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert len(rows) == 2


def test_get_marginalia_by_uuid(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    fetched = get_marginalia_impl(lib.session, uuid=created["uuid"])
    assert fetched["uuid"] == created["uuid"]


def test_update_marginalia(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    updated = update_marginalia_impl(
        lib.session, uuid=created["uuid"], color="#ff0000"
    )
    assert updated["color"] == "#ff0000"


def test_soft_delete_and_restore(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    uuid = created["uuid"]

    delete_marginalia_impl(lib.session, uuid=uuid)
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid not in {r["uuid"] for r in rows}

    restore_marginalia_impl(lib.session, uuid=uuid)
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid in {r["uuid"] for r in rows}


def test_hard_delete(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    uuid = created["uuid"]
    delete_marginalia_impl(lib.session, uuid=uuid, hard=True)
    with pytest.raises(LookupError):
        get_marginalia_impl(lib.session, uuid=uuid)


def test_add_rejects_invalid_uri(lib_and_book):
    lib, _ = lib_and_book
    with pytest.raises(ValueError):
        add_marginalia_impl(lib.session, book_uris=["not-a-uri"], content="x")
