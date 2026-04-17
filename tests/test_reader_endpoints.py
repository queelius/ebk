"""Tests for browser-reader endpoints: /read, /books/{id}/file, /books/{id}/metadata.json."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def client_with_epub(sample_epub):
    """Import the conftest sample EPUB into a temp library and yield TestClient + book."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    book = lib.add_book(
        sample_epub,
        metadata={"title": "Phase 2 Sample", "creators": ["Test Author"]},
        extract_text=False,
        extract_cover=False,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client_with_txt():
    """Import a .txt file (unsupported reader format) and yield TestClient + book."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    txt_file = temp_dir / "notes.txt"
    txt_file.write_text("Just a plain text file for testing.")
    book = lib.add_book(
        txt_file,
        metadata={"title": "Plain Notes", "creators": ["Nobody"]},
        extract_text=False,
        extract_cover=False,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


# ── GET /read/{book_id} ─────────────────────────────────────


def test_read_epub_returns_html(client_with_epub):
    client, book, _ = client_with_epub
    r = client.get(f"/read/{book.id}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "window.BOOK" in r.text
    assert "epub" in r.text.lower()


def test_read_epub_contains_book_metadata(client_with_epub):
    client, book, _ = client_with_epub
    r = client.get(f"/read/{book.id}")
    assert r.status_code == 200
    # Title should appear in the page
    assert book.title in r.text
    # The injected JSON should contain the book id
    assert f'"id": {book.id}' in r.text or f'"id":{book.id}' in r.text


def test_read_nonexistent_book_returns_404(client_with_epub):
    client, _, _ = client_with_epub
    r = client.get("/read/99999")
    assert r.status_code == 404


def test_read_unsupported_format_returns_error(client_with_txt):
    client, book, _ = client_with_txt
    r = client.get(f"/read/{book.id}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "not supported" in r.text.lower()


# ── GET /books/{book_id}/file ────────────────────────────────


def test_file_endpoint_streams_epub(client_with_epub):
    client, book, _ = client_with_epub
    r = client.get(f"/books/{book.id}/file")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    assert "epub" in ct or "octet-stream" in ct
    assert len(r.content) > 0


def test_file_endpoint_supports_range(client_with_epub):
    client, book, _ = client_with_epub
    r = client.get(f"/books/{book.id}/file", headers={"Range": "bytes=0-99"})
    # FileResponse returns 200 or 206 depending on Starlette version
    assert r.status_code in (200, 206)
    assert len(r.content) > 0


def test_file_endpoint_404_for_missing_book(client_with_epub):
    client, _, _ = client_with_epub
    r = client.get("/books/99999/file")
    assert r.status_code == 404


# ── GET /books/{book_id}/metadata.json ───────────────────────


def test_metadata_json(client_with_epub):
    client, book, _ = client_with_epub
    r = client.get(f"/books/{book.id}/metadata.json")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == book.title
    assert "format" in data
    assert "book_uri" in data


def test_metadata_json_404(client_with_epub):
    client, _, _ = client_with_epub
    r = client.get("/books/99999/metadata.json")
    assert r.status_code == 404
