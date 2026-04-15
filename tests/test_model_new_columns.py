"""Test ORM visibility of new columns and URI properties."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import Book, Marginalia, ReadingSession, PersonalMetadata, utc_now
from book_memex.core.uri import parse_uri


@pytest.fixture
def temp_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def _add_sample_book(lib):
    p = lib.library_path / "sample.txt"
    p.write_text("hello")
    return lib.add_book(
        p,
        metadata={"title": "Sample", "creators": ["Author"]},
        extract_text=False,
    )


def test_marginalia_round_trips_new_columns(temp_library):
    book = _add_sample_book(temp_library)
    m = Marginalia(
        content="note",
        highlighted_text="passage",
        color="#ffff00",
        position={"cfi": "epubcfi(...)"},
    )
    m.books.append(book)
    temp_library.session.add(m)
    temp_library.session.commit()

    fetched = temp_library.session.get(Marginalia, m.id)
    assert fetched.uuid is not None
    assert len(fetched.uuid) == 32  # uuid4().hex
    assert fetched.color == "#ffff00"
    assert fetched.archived_at is None
    assert fetched.position == {"cfi": "epubcfi(...)"}


def test_marginalia_uri_property(temp_library):
    m = Marginalia(content="x")
    temp_library.session.add(m)
    temp_library.session.commit()
    parsed = parse_uri(m.uri)
    assert parsed.kind == "marginalia"
    assert parsed.id == m.uuid


def test_reading_session_new_columns(temp_library):
    book = _add_sample_book(temp_library)
    rs = ReadingSession(
        book_id=book.id,
        start_time=utc_now(),
        start_anchor={"cfi": "epubcfi(/6/4!/4)"},
    )
    temp_library.session.add(rs)
    temp_library.session.commit()

    fetched = temp_library.session.get(ReadingSession, rs.id)
    assert fetched.uuid is not None
    assert fetched.start_anchor == {"cfi": "epubcfi(/6/4!/4)"}
    assert fetched.end_anchor is None
    assert fetched.archived_at is None


def test_reading_session_uri_property(temp_library):
    book = _add_sample_book(temp_library)
    rs = ReadingSession(book_id=book.id, start_time=utc_now())
    temp_library.session.add(rs)
    temp_library.session.commit()
    parsed = parse_uri(rs.uri)
    assert parsed.kind == "reading"
    assert parsed.id == rs.uuid


def test_book_uri_property(temp_library):
    book = _add_sample_book(temp_library)
    parsed = parse_uri(book.uri)
    assert parsed.kind == "book"
    assert parsed.id == book.unique_id


def test_personal_metadata_progress_anchor(temp_library):
    book = _add_sample_book(temp_library)
    pm = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
    if pm is None:
        pm = PersonalMetadata(book_id=book.id)
        temp_library.session.add(pm)
    pm.progress_anchor = {"cfi": "epubcfi(/6/4!/6)", "percentage": 45}
    temp_library.session.commit()

    fetched = temp_library.session.get(PersonalMetadata, pm.id)
    assert fetched.progress_anchor == {"cfi": "epubcfi(/6/4!/6)", "percentage": 45}
