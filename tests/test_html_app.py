"""Tests for the single-file HTML SPA exporter (C6 workspace contract).

Shape: one self-contained .html file with inlined sql-wasm.js,
base64-encoded sql-wasm.wasm, and gzipped+base64 SQLite DB. All
user data reaches the DOM via textContent; no CDN, no fetch, no FTS5
in the shipped DB (vendored sql.js lacks FTS5).
"""

from __future__ import annotations

import base64
import gzip
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from book_memex.exports.html_app import export_html_app
from book_memex.library_db import Library


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lib_with_data():
    """Library populated with one book and one marginalia linked to it."""
    from book_memex.services.marginalia_service import MarginaliaService

    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)

    p = lib.library_path / "b.txt"
    p.write_text("hello")
    book = lib.add_book(
        p,
        metadata={
            "title": "The Example",
            "creators": ["A. Author"],
            "subjects": ["Fiction"],
            "language": "en",
        },
        extract_text=False,
        extract_cover=False,
    )
    svc = MarginaliaService(lib.session)
    m = svc.create(
        content="a note",
        highlighted_text="key passage",
        book_ids=[book.id],
        page_number=7,
        color="#ffff00",
    )

    info = {
        "unique_id": book.unique_id,
        "marginalia_uuid": m.uuid,
    }
    yield lib, info
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def _extract_db_from_html(html: str) -> bytes:
    """Pull the gzipped+base64 DB out of the SPA and decompress it."""
    match = re.search(
        r'<script id="bm-db-b64" type="application/base64">\s*'
        r'([A-Za-z0-9+/=\s]+?)\s*</script>',
        html,
    )
    assert match is not None, "bm-db-b64 script not found"
    gz = base64.b64decode("".join(match.group(1).split()))
    return gzip.decompress(gz)


# ---------------------------------------------------------------------------
# HtmlAppExporter
# ---------------------------------------------------------------------------


class TestHtmlAppExporter:
    def test_creates_single_html_file(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        result = lib.export_html_app(out)
        assert Path(result["path"]).exists()
        assert out.is_file()
        # Nothing else produced — single-file contract.
        assert list(out.parent.iterdir()) == [out]

    def test_auto_appends_html_extension(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive"
        result = lib.export_html_app(out)
        assert Path(result["path"]).suffix == ".html"

    def test_inlines_vendored_sqljs(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        assert "initSqlJs" in html
        for smell in ("cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com"):
            assert smell not in html

    def test_embeds_wasm_as_base64(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        m = re.search(
            r'<script id="bm-wasm-b64" type="application/base64">\s*'
            r'([A-Za-z0-9+/=\s]+?)\s*</script>',
            html,
        )
        assert m is not None
        blob = base64.b64decode("".join(m.group(1).split()))
        assert blob[:4] == b"\x00asm"
        assert len(blob) > 100_000

    def test_embeds_gzipped_db(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        m = re.search(
            r'<script id="bm-db-b64" type="application/base64">\s*'
            r'([A-Za-z0-9+/=\s]+?)\s*</script>',
            html,
        )
        assert m is not None
        gz = base64.b64decode("".join(m.group(1).split()))
        assert gz[:2] == b"\x1f\x8b"
        raw = gzip.decompress(gz)
        assert raw[:16].startswith(b"SQLite format 3")

    def test_shipped_db_has_no_fts5(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        db_bytes = _extract_db_from_html(out.read_text())
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(db_bytes)
            tmp_db = f.name
        try:
            conn = sqlite3.connect(tmp_db)
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            conn.close()
        finally:
            Path(tmp_db).unlink()
        assert "books_fts" not in names
        assert "book_content_fts" not in names
        # Denormalized schema we actually ship:
        assert "books" in names
        assert "marginalia" in names
        assert "reading_sessions" in names

    def test_shipped_db_contains_library_data(self, lib_with_data, tmp_path):
        lib, info = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        db_bytes = _extract_db_from_html(out.read_text())
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(db_bytes)
            tmp_db = f.name
        try:
            conn = sqlite3.connect(tmp_db)
            rows = list(
                conn.execute(
                    "SELECT unique_id, title, authors_json, subjects_json "
                    "FROM books WHERE archived_at IS NULL"
                )
            )
            conn.close()
        finally:
            Path(tmp_db).unlink()
        assert len(rows) == 1
        uid, title, authors_json, subjects_json = rows[0]
        assert uid == info["unique_id"]
        assert title == "The Example"
        assert "A. Author" in json.loads(authors_json)
        assert "Fiction" in json.loads(subjects_json)

    def test_shipped_db_links_marginalia_to_book(self, lib_with_data, tmp_path):
        lib, info = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        db_bytes = _extract_db_from_html(out.read_text())
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(db_bytes)
            tmp_db = f.name
        try:
            conn = sqlite3.connect(tmp_db)
            rows = list(
                conn.execute(
                    "SELECT uuid, content, book_unique_ids_json "
                    "FROM marginalia WHERE archived_at IS NULL"
                )
            )
            conn.close()
        finally:
            Path(tmp_db).unlink()
        assert len(rows) == 1
        uuid, content, book_uids_json = rows[0]
        assert uuid == info["marginalia_uuid"]
        assert content == "a note"
        assert info["unique_id"] in json.loads(book_uids_json)

    def test_hash_routing_present(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        for route in ("#/book/", "#/tag/", "#/subject/", "#/author/", "#/search/", "#/marginalia"):
            assert route in html, f"expected route token {route} in HTML"
        assert "hashchange" in html

    def test_ui_elements_present(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        assert 'id="search"' in html
        assert 'id="stats"' in html
        assert 'id="theme-toggle"' in html
        assert 'id="brand"' in html
        assert 'id="view"' in html

    def test_warm_palette_variables_present(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()
        for var in ("--text-accent", "--bg-surface", "--badge-bg", "--font-serif"):
            assert var in html, f"missing CSS custom property {var}"

    def test_empty_library_exports_cleanly(self, tmp_path):
        """Exporting an empty library should still produce a valid single-file HTML."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            lib = Library.open(temp_dir)
            out = tmp_path / "empty.html"
            result = lib.export_html_app(out)
            assert Path(result["path"]).exists()
            db_bytes = _extract_db_from_html(out.read_text())
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                f.write(db_bytes)
                tmp_db = f.name
            try:
                conn = sqlite3.connect(tmp_db)
                count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
                conn.close()
            finally:
                Path(tmp_db).unlink()
            assert count == 0
            lib.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_report_shows_size_stats(self, lib_with_data, tmp_path):
        lib, _ = lib_with_data
        out = tmp_path / "archive.html"
        result = lib.export_html_app(out)
        assert result["original_db_bytes"] > 0
        assert result["embedded_db_bytes"] > 0
        assert result["embedded_db_bytes"] <= result["original_db_bytes"]
        assert result["html_bytes"] >= result["embedded_db_bytes"]


# ---------------------------------------------------------------------------
# Soft-deleted records must not ship in the SPA (regression: R2, data-loss)
# ---------------------------------------------------------------------------


class TestHtmlAppExcludesArchived:
    """An archived book / marginalia / reading session must not be exported."""

    @staticmethod
    def _shipped(html: str, table: str, col: str):
        db = _extract_db_from_html(html)
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.write(db)
        f.close()
        conn = sqlite3.connect(f.name)
        try:
            return [r[0] for r in conn.execute(f"SELECT {col} FROM {table}")]
        finally:
            conn.close()
            Path(f.name).unlink()

    def test_archived_records_absent_from_export(self, lib_with_data, tmp_path):
        from datetime import datetime

        from book_memex.services.marginalia_service import MarginaliaService
        from book_memex.services.reading_session_service import (
            ReadingSessionService,
        )

        lib, info = lib_with_data

        # A second book, archived.
        p = lib.library_path / "secret.txt"
        p.write_text("private")
        arch_book = lib.add_book(
            p,
            metadata={"title": "Archived Secret", "language": "en"},
            extract_text=False,
            extract_cover=False,
        )
        arch_book_uid = arch_book.unique_id
        arch_book.archived_at = datetime.utcnow()

        m_svc = MarginaliaService(lib.session)
        arch_m = m_svc.create(content="deleted note", book_ids=[arch_book.id])
        arch_m_uuid = arch_m.uuid
        m_svc.archive(arch_m)

        r_svc = ReadingSessionService(lib.session)
        arch_rs = r_svc.start(book_id=arch_book.id)
        r_svc.end(arch_rs.uuid)
        arch_rs_uuid = arch_rs.uuid
        r_svc.archive(arch_rs)
        lib.session.commit()

        out = tmp_path / "archive.html"
        lib.export_html_app(out)
        html = out.read_text()

        books = self._shipped(html, "books", "unique_id")
        assert arch_book_uid not in books
        assert info["unique_id"] in books

        marg = self._shipped(html, "marginalia", "uuid")
        assert arch_m_uuid not in marg
        assert info["marginalia_uuid"] in marg

        # This fixture has no non-archived reading session, so we only assert
        # the archived one is excluded.
        reading = self._shipped(html, "reading_sessions", "uuid")
        assert arch_rs_uuid not in reading
