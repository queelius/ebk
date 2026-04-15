"""Tests for MarginaliaService's extended API (soft-delete, scope filter, uuid)."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.services.marginalia_service import MarginaliaService


@pytest.fixture
def lib_with_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"
    p.write_text("hello")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_with_color(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(
        content="note",
        highlighted_text="passage",
        book_ids=[book.id],
        page_number=5,
        color="#ff0000",
    )
    assert m.color == "#ff0000"
    assert m.uuid is not None


def test_scope_derivation(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    # Collection note (0 books)
    m0 = svc.create(content="c")
    assert m0.scope == "collection_note"
    # Book note (1 book, no location)
    m1 = svc.create(content="bn", book_ids=[book.id])
    assert m1.scope == "book_note"
    # Highlight (1 book + location)
    m2 = svc.create(content="h", book_ids=[book.id], page_number=3)
    assert m2.scope == "highlight"


def test_list_for_book_filters_archived_by_default(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m1 = svc.create(content="a", book_ids=[book.id])
    m2 = svc.create(content="b", book_ids=[book.id])
    svc.archive(m2)

    active = svc.list_for_book(book.id)
    assert m1.id in {m.id for m in active}
    assert m2.id not in {m.id for m in active}

    with_archived = svc.list_for_book(book.id, include_archived=True)
    assert {m1.id, m2.id}.issubset({m.id for m in with_archived})


def test_list_for_book_with_scope_filter(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    bn = svc.create(content="bn", book_ids=[book.id])
    hl = svc.create(content="h", book_ids=[book.id], page_number=1)

    highlights = svc.list_for_book(book.id, scope="highlight")
    assert hl.id in {m.id for m in highlights}
    assert bn.id not in {m.id for m in highlights}


def test_get_by_uuid(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(content="x", book_ids=[book.id])
    fetched = svc.get_by_uuid(m.uuid)
    assert fetched is not None
    assert fetched.id == m.id


def test_archive_restore_cycle(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(content="x", book_ids=[book.id])
    svc.archive(m)
    assert m.archived_at is not None
    svc.restore(m)
    assert m.archived_at is None
