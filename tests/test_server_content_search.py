"""Integration tests for /api/books/{id}/search and /api/search/content."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library


@pytest.fixture
def client_with_indexed_book(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "a.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(dest, metadata={"title": "A", "creators": ["X"]}, extract_text=True)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_within_book_search_returns_hits(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=Bayesian")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    top = data[0]
    assert "snippet" in top
    assert "segment_type" in top
    assert "segment_index" in top
    assert "anchor" in top
    assert "fragment" in top
    assert top["fragment"].startswith("epubcfi(") or top["fragment"].startswith("page=")


def test_within_book_search_empty_query_returns_400(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=")
    assert r.status_code == 400


def test_within_book_search_limit(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=a&limit=1")
    assert r.status_code == 200
    assert len(r.json()) <= 1


def test_cross_library_content_search(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get("/api/search/content?q=Bayesian")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    top = data[0]
    assert top["book_id"] == book.id
    assert top["book_uri"].startswith("book-memex://book/")
    assert "fragment" in top


def test_cross_library_search_no_matches_empty(client_with_indexed_book):
    client, _, _ = client_with_indexed_book
    r = client.get("/api/search/content?q=xenomorph_never_present")
    assert r.status_code == 200
    assert r.json() == []
