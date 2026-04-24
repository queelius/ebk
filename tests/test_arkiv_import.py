"""Tests for the arkiv importer (book_memex.services.arkiv_import).

Covers bundle format auto-detection (directory / .zip / .tar.gz /
.jsonl / .jsonl.gz), round-trip through the exporter, UUID-stable
marginalia round-trip, unique_id-stable book round-trip, and
idempotent re-imports.
"""

from __future__ import annotations

import gzip
import json
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select

from book_memex.db.models import Book, Marginalia, ReadingSession
from book_memex.library_db import Library
from book_memex.services.arkiv_import import (
    _is_book_memex_arkiv_record,
    _parse_timestamp,
    _unique_id_from_book_uri,
    detect,
    import_arkiv,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lib_with_data():
    """Library populated with one book, one marginalia, one reading session."""
    from book_memex.services.marginalia_service import MarginaliaService
    from book_memex.services.reading_session_service import ReadingSessionService

    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)

    p = lib.library_path / "b.txt"
    p.write_text("h")
    book = lib.add_book(
        p,
        metadata={
            "title": "Sample Book",
            "creators": ["Test Author"],
            "subjects": ["Fiction", "Adventure"],
            "language": "en",
        },
        extract_text=False,
        extract_cover=False,
    )

    m_svc = MarginaliaService(lib.session)
    r_svc = ReadingSessionService(lib.session)
    m = m_svc.create(
        content="this is my note",
        highlighted_text="quoted passage",
        book_ids=[book.id],
        page_number=42,
        color="#ffff00",
    )
    rs = r_svc.start(book_id=book.id, start_anchor={"cfi": "start"})
    r_svc.end(rs.uuid, end_anchor={"cfi": "end"})

    # Capture ids/uuids *inside* the session since ORM lazy loads expire.
    info = {
        "unique_id": book.unique_id,
        "book_uri": book.uri,
        "marginalia_uuid": m.uuid,
        "marginalia_uri": m.uri,
        "reading_uuid": rs.uuid,
    }

    yield lib, info

    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def fresh_lib():
    """An empty Library for receiving imports."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# _parse_timestamp / _is_book_memex_arkiv_record / _unique_id_from_book_uri
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_parse_timestamp_iso(self):
        ts = _parse_timestamp("2026-04-23T12:34:56")
        assert ts is not None
        assert ts.hour == 12

    def test_parse_timestamp_none(self):
        assert _parse_timestamp(None) is None
        assert _parse_timestamp("") is None

    def test_is_record_accepts_book(self):
        assert _is_book_memex_arkiv_record(
            {"kind": "book", "uri": "book-memex://book/abc", "unique_id": "abc"}
        )

    def test_is_record_accepts_marginalia(self):
        assert _is_book_memex_arkiv_record(
            {"kind": "marginalia", "uri": "book-memex://marginalia/u", "uuid": "u"}
        )

    def test_is_record_accepts_reading(self):
        assert _is_book_memex_arkiv_record(
            {"kind": "reading", "uri": "book-memex://reading/u", "uuid": "u"}
        )

    def test_is_record_rejects_unknown_kind(self):
        assert not _is_book_memex_arkiv_record({"kind": "photo"})

    def test_is_record_rejects_non_dict(self):
        assert not _is_book_memex_arkiv_record("foo")  # type: ignore[arg-type]

    def test_unique_id_from_book_uri_normal(self):
        assert _unique_id_from_book_uri("book-memex://book/abc123") == "abc123"

    def test_unique_id_from_book_uri_with_fragment(self):
        assert (
            _unique_id_from_book_uri("book-memex://book/abc123#page=1")
            == "abc123"
        )

    def test_unique_id_from_book_uri_rejects_wrong_scheme(self):
        assert _unique_id_from_book_uri("file:///tmp/foo") is None

    def test_unique_id_from_book_uri_none(self):
        assert _unique_id_from_book_uri(None) is None


# ---------------------------------------------------------------------------
# detect(): every bundle shape
# ---------------------------------------------------------------------------


class TestDetect:
    def test_detect_directory(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)
        assert detect(out) is True

    def test_detect_zip(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "bundle.zip"
        lib.export_arkiv(out)
        assert detect(out) is True

    def test_detect_tar_gz(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "bundle.tar.gz"
        lib.export_arkiv(out)
        assert detect(out) is True

    def test_detect_tgz(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "bundle.tgz"
        lib.export_arkiv(out)
        assert detect(out) is True

    def test_detect_bare_jsonl(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        dir_out = tmp_path / "d"
        lib.export_arkiv(dir_out)
        bare = tmp_path / "records.jsonl"
        bare.write_bytes((dir_out / "records.jsonl").read_bytes())
        assert detect(bare) is True

    def test_detect_bare_jsonl_gz(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        dir_out = tmp_path / "d"
        lib.export_arkiv(dir_out)
        bare_gz = tmp_path / "records.jsonl.gz"
        with gzip.open(bare_gz, "wb") as f:
            f.write((dir_out / "records.jsonl").read_bytes())
        assert detect(bare_gz) is True

    def test_detect_rejects_missing_path(self, tmp_path):
        assert detect(tmp_path / "does-not-exist") is False

    def test_detect_rejects_foreign_jsonl(self, tmp_path):
        foreign = tmp_path / "foreign.jsonl"
        foreign.write_text(
            json.dumps({"kind": "photo", "uri": "photo-memex://photo/abc"}) + "\n"
        )
        assert detect(foreign) is False

    def test_detect_rejects_non_jsonl_file(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")
        assert detect(txt) is False


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestImportRoundTrip:
    def test_import_directory_reconstructs_book(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        lib, info = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)

        stats = import_arkiv(fresh_lib, out)
        assert stats["books_added"] == 1
        assert stats["books_seen"] == 1
        assert stats["marginalia_added"] == 1
        assert stats["reading_added"] == 1

        imported = fresh_lib.get_book_by_unique_id(info["unique_id"])
        assert imported is not None
        assert imported.title == "Sample Book"
        assert any(a.name == "Test Author" for a in imported.authors)
        assert {s.name for s in imported.subjects} == {"Fiction", "Adventure"}
        assert imported.language == "en"

    def test_import_zip_bundle(self, lib_with_data, fresh_lib, tmp_path):
        lib, info = lib_with_data
        out = tmp_path / "bundle.zip"
        lib.export_arkiv(out)
        stats = import_arkiv(fresh_lib, out)
        assert stats["books_added"] == 1
        assert stats["marginalia_added"] == 1

    def test_import_tar_gz_bundle(self, lib_with_data, fresh_lib, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "bundle.tar.gz"
        lib.export_arkiv(out)
        stats = import_arkiv(fresh_lib, out)
        assert stats["books_added"] == 1
        assert stats["reading_added"] == 1

    def test_import_bare_jsonl_gz(self, lib_with_data, fresh_lib, tmp_path):
        """SPA round-trip format: bare .jsonl.gz."""
        lib, _ = lib_with_data
        dir_out = tmp_path / "d"
        lib.export_arkiv(dir_out)
        bare_gz = tmp_path / "records.jsonl.gz"
        with gzip.open(bare_gz, "wb") as f:
            f.write((dir_out / "records.jsonl").read_bytes())

        stats = import_arkiv(fresh_lib, bare_gz)
        assert stats["books_added"] == 1
        assert stats["marginalia_added"] == 1

    def test_marginalia_uuid_preserved(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        lib, info = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)
        import_arkiv(fresh_lib, out)

        m = fresh_lib.session.execute(
            select(Marginalia).where(Marginalia.uuid == info["marginalia_uuid"])
        ).scalar_one_or_none()
        assert m is not None
        assert m.content == "this is my note"
        assert m.color == "#ffff00"

    def test_reading_session_uuid_preserved(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        lib, info = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)
        import_arkiv(fresh_lib, out)

        rs = fresh_lib.session.execute(
            select(ReadingSession).where(
                ReadingSession.uuid == info["reading_uuid"]
            )
        ).scalar_one_or_none()
        assert rs is not None
        assert rs.start_anchor == {"cfi": "start"}
        assert rs.end_anchor == {"cfi": "end"}

    def test_marginalia_links_to_imported_book(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        lib, info = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)
        import_arkiv(fresh_lib, out)

        m = fresh_lib.session.execute(
            select(Marginalia).where(Marginalia.uuid == info["marginalia_uuid"])
        ).scalar_one_or_none()
        assert m is not None
        assert any(
            b.unique_id == info["unique_id"] for b in m.books
        ), "imported marginalia should link to the imported book"

    def test_re_import_is_idempotent(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        lib, _ = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)

        first = import_arkiv(fresh_lib, out)
        second = import_arkiv(fresh_lib, out)

        assert first["books_added"] == 1
        assert second["books_added"] == 0
        assert second["books_skipped_existing"] == 1
        assert second["marginalia_skipped_existing"] == 1
        assert second["reading_skipped_existing"] == 1

        # No duplicates in the DB.
        assert (
            len(list(fresh_lib.session.execute(select(Book)).scalars())) == 1
        )
        assert (
            len(
                list(fresh_lib.session.execute(select(Marginalia)).scalars())
            )
            == 1
        )
        assert (
            len(
                list(
                    fresh_lib.session.execute(select(ReadingSession)).scalars()
                )
            )
            == 1
        )

    def test_merge_flag_accepted(self, lib_with_data, fresh_lib, tmp_path):
        """--merge is accepted and behaves the same as default today."""
        lib, _ = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)
        stats = import_arkiv(fresh_lib, out, merge=True)
        assert stats["books_added"] == 1

    def test_orphan_reading_session_skipped(self, fresh_lib, tmp_path):
        """A reading-session record with no matching book is counted as orphaned."""
        bundle = tmp_path / "orphan.jsonl"
        orphan_record = {
            "kind": "reading",
            "uri": "book-memex://reading/deadbeef",
            "uuid": "deadbeef",
            "book_uri": "book-memex://book/missing123",
            "start_time": "2026-01-01T12:00:00",
            "end_time": None,
            "start_anchor": None,
            "end_anchor": None,
            "pages_read": None,
        }
        bundle.write_text(json.dumps(orphan_record) + "\n")

        stats = import_arkiv(fresh_lib, bundle)
        assert stats["reading_orphaned"] == 1
        assert stats["reading_added"] == 0

    def test_library_import_arkiv_convenience_method(
        self, lib_with_data, fresh_lib, tmp_path
    ):
        """Library.import_arkiv(...) forwards to the service function."""
        lib, _ = lib_with_data
        out = tmp_path / "bundle"
        lib.export_arkiv(out)

        stats = fresh_lib.import_arkiv(out)
        assert stats["books_added"] == 1
        assert stats["marginalia_added"] == 1
