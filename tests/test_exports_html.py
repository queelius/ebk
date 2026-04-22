"""Tests for the self-contained HTML library export."""
import shutil
import tempfile
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.services.marginalia_service import MarginaliaService
from book_memex.exports.html_library import export_to_html


@pytest.fixture
def lib_with_annotated_book():
    """A library with one book carrying a highlight and a book-level note."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"
    p.write_text("hello")
    book = lib.add_book(
        p,
        metadata={"title": "Annotated Book", "creators": ["X"]},
        extract_text=False,
    )

    svc = MarginaliaService(lib.session, lib.library_path)
    svc.create(
        content="My reaction to this passage.",
        highlighted_text="deliberate practice",
        book_ids=[book.id],
        page_number=42,
        color="#ffff00",
    )
    svc.create(
        content="Overall thoughts on the book.",
        book_ids=[book.id],
    )
    lib.session.refresh(book)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_exported_html_includes_book_marginalia(tmp_path, lib_with_annotated_book):
    """Highlights and book-notes for a book must appear in the exported HTML."""
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)

    html = output.read_text()

    # Highlighted passage appears verbatim.
    assert "deliberate practice" in html, (
        "highlighted_text must appear in exported HTML"
    )
    # Note attached to the highlight appears verbatim.
    assert "My reaction to this passage." in html, (
        "note content attached to highlight must appear in exported HTML"
    )
    # Book-level note (no location) also appears.
    assert "Overall thoughts on the book." in html, (
        "book_note content must appear in exported HTML"
    )


def test_exported_html_omits_archived_marginalia(tmp_path, lib_with_annotated_book):
    """Archived marginalia must NOT appear in the exported HTML."""
    lib, book = lib_with_annotated_book
    svc = MarginaliaService(lib.session, lib.library_path)

    # Add an archived entry that should not leak into the export.
    archived = svc.create(
        content="Archived thought that should stay hidden.",
        highlighted_text="secret archived quote",
        book_ids=[book.id],
        page_number=7,
    )
    svc.archive(archived)
    lib.session.refresh(book)

    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    assert "Archived thought that should stay hidden." not in html
    assert "secret archived quote" not in html
    # Sanity: live marginalia still present so we know export ran.
    assert "deliberate practice" in html


def test_exported_html_wires_marginalia_into_modal(tmp_path, lib_with_annotated_book):
    """The book-detail modal must render marginalia, not merely embed the JSON.

    The JS `showDetails` path must include a loop over `book.marginalia` that
    produces a structurally-recognizable block (identified by a reserved CSS
    class), so readers can see their highlights and notes when they open a
    book, not just grep the raw file.
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    # The modal renderer must iterate over book.marginalia.
    assert "book.marginalia.map" in html, (
        "modal renderer must iterate over book.marginalia"
    )
    # A reserved CSS class identifies a rendered marginalia entry, anchoring
    # styling and any future JS hooks.
    assert "marginalia-entry" in html, (
        "rendered marginalia must have a dedicated CSS class"
    )


def test_table_rows_are_row_level_clickable(tmp_path, lib_with_annotated_book):
    """In table view, the whole <tr> must open the detail modal.

    The previous behavior wired onclick only on the title <span>, leaving the
    author / year / format / rating cells inert. Users who clicked a row but
    missed the title got no feedback. Row-level click is consistent with grid
    and list views (both wire onclick on the outer card).
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    assert '<tr onclick="showDetails(' in html, (
        "table <tr> must wire the detail modal at the row level, not just on "
        "the title cell"
    )


def test_exported_html_without_marginalia_renders(tmp_path):
    """Books without any marginalia must still export cleanly (no marginalia section)."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        lib = Library.open(temp_dir)
        p = lib.library_path / "b.txt"
        p.write_text("hello")
        book = lib.add_book(
            p,
            metadata={"title": "Unannotated", "creators": ["Y"]},
            extract_text=False,
        )

        output = tmp_path / "library.html"
        export_to_html([book], output)
        html = output.read_text()
        assert "Unannotated" in html
    finally:
        lib.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
