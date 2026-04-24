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


# ---------------------------------------------------------------------------
# C9: marginalia orphan survival across hard-delete of a book.
#
# The marginalia_books association table uses ON DELETE CASCADE on both
# FK columns, which removes the *link row* when either side is deleted.
# The marginalia row itself is on a separate table with no direct FK to
# books, so it survives. Cross-book marginalia (linked to multiple
# books) keep their remaining links intact.
# ---------------------------------------------------------------------------


def test_marginalia_survives_book_hard_delete(lib_with_book):
    """Hard-deleting a book removes the link but keeps the marginalia row."""
    from sqlalchemy import select

    from book_memex.db.models import Book, Marginalia

    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    note = svc.create(
        content="a note about this book",
        book_ids=[book.id],
    )
    note_uuid = note.uuid
    book_id = book.id

    # Hard delete via session to exercise the DB-level CASCADE.
    target = lib.session.get(Book, book_id)
    assert target is not None
    lib.session.delete(target)
    lib.session.commit()

    # Marginalia row is still there, just unlinked.
    survived = lib.session.execute(
        select(Marginalia).where(Marginalia.uuid == note_uuid)
    ).scalar_one_or_none()
    assert survived is not None, "marginalia must survive book hard delete"
    assert list(survived.books) == [], (
        "association rows should have been cascade-deleted, leaving the "
        "marginalia row detached rather than dangling"
    )


def test_cross_book_marginalia_keeps_other_links(lib_with_book):
    """Deleting one of N books leaves the marginalia linked to the other N-1."""
    from sqlalchemy import select

    from book_memex.db.models import Book, Marginalia

    lib, book_a = lib_with_book
    # Add a second book so we have a cross-book marginalia target.
    p = lib.library_path / "c.txt"
    p.write_text("another")
    book_b = lib.add_book(
        p, metadata={"title": "C", "creators": ["Y"]}, extract_text=False
    )

    svc = MarginaliaService(lib.session, lib.library_path)
    note = svc.create(
        content="observation spanning two books",
        book_ids=[book_a.id, book_b.id],
    )
    note_uuid = note.uuid
    keep_uid = book_b.unique_id

    # Hard delete book_a.
    target = lib.session.get(Book, book_a.id)
    assert target is not None
    lib.session.delete(target)
    lib.session.commit()

    # The marginalia row keeps its link to book_b; only the row for
    # book_a in marginalia_books is gone.
    survived = lib.session.execute(
        select(Marginalia).where(Marginalia.uuid == note_uuid)
    ).scalar_one_or_none()
    assert survived is not None
    remaining_uids = {b.unique_id for b in survived.books}
    assert remaining_uids == {keep_uid}
