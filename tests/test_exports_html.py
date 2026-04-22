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


def test_book_description_is_html_escaped_in_modal(tmp_path):
    """book.description must flow through escapeHtml in the modal template.

    Publisher-supplied descriptions cannot be trusted. Escaping matches the
    policy applied to marginalia content and protects deployments that host
    the exported HTML on the web (e.g. via the Hugo deployment path the
    README documents).
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        lib = Library.open(temp_dir)
        p = lib.library_path / "b.txt"
        p.write_text("hello")
        book = lib.add_book(
            p,
            metadata={"title": "XSS Test", "creators": ["X"]},
            extract_text=False,
        )
        book.description = "<script>window.__xss = true;</script>Plain tail."
        lib.session.commit()

        output = tmp_path / "library.html"
        export_to_html([book], output)
        html = output.read_text()

        assert "escapeHtml(book.description)" in html, (
            "book.description must be passed through escapeHtml in "
            "showDetails() to prevent XSS"
        )
    finally:
        lib.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_grid_card_shows_marginalia_count_badge(tmp_path, lib_with_annotated_book):
    """Books with marginalia show a count badge on their grid card.

    This lets users see at a glance which books they've annotated without
    having to open each detail modal. Implemented as a small positioned
    badge on the cover; presence is asserted via the reserved CSS class.
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    assert ".marginalia-badge" in html, (
        "grid card render must use a .marginalia-badge CSS class for the count"
    )
    assert "book.marginalia.length" in html, (
        "grid card render must reference book.marginalia.length"
    )


def test_table_view_has_notes_column(tmp_path, lib_with_annotated_book):
    """Table view must include a Notes column showing marginalia count per book.

    Mirrors the grid card badge for the info-dense view. Scannable at a
    glance without opening the modal.
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    assert ">Notes<" in html, (
        "renderTable must have a Notes column header"
    )


def test_library_wide_notes_view_mode_is_wired(tmp_path, lib_with_annotated_book):
    """A 4th view mode aggregates marginalia across every book into one list.

    Grid / List / Table are book-oriented. The Notes view is annotation-
    oriented: a flat scrolling list across the library, filterable by scope.
    This is the surface where cross-book and collection notes (which don't
    belong to any single book) become first-class.
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    # Toolbar button with a reserved title.
    assert 'title="Notes View"' in html, (
        "toolbar must include a Notes View toggle button"
    )
    # Renderer aggregates marginalia across all books.
    assert "renderNotesView" in html, (
        "a renderNotesView function must aggregate marginalia across books"
    )


def test_notes_view_renders_entries_with_book_source(tmp_path, lib_with_annotated_book):
    """Notes view entries must link back to the book they belong to.

    Without a source reference, an aggregated marginalia list is useless for
    navigating back to the passage. Each entry must carry the book's title
    (as text) and a click-through to showDetails().
    """
    lib, book = lib_with_annotated_book
    output = tmp_path / "library.html"
    export_to_html([book], output)
    html = output.read_text()

    # The notes-view render path builds entries with a source link.
    assert "marginalia-source" in html, (
        "notes-view entries must carry a .marginalia-source link back to the book"
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
