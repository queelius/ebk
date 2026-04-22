"""Phase 2 end-to-end test covering extraction and search."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library
from book_memex.mcp.tools import (
    search_library_content_impl, get_segments_impl,
)


@pytest.fixture
def e2e_env(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "book.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(
        dest,
        metadata={"title": "Phase 2 Test", "creators": ["Author"]},
        extract_text=True,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_indexes_content_and_search(e2e_env):
    client, book, lib = e2e_env

    # 1. Content was indexed on import.
    segs = get_segments_impl(lib.session, book_id=book.id)
    assert len(segs) == 3
    assert segs[0]["segment_type"] == "chapter"

    # 2. Within-book search via REST returns at least one hit for a chapter term.
    r = client.get(f"/api/books/{book.id}/search?q=Bayesian")
    assert r.status_code == 200
    hits = r.json()
    assert any("Bayesian" in (h.get("title") or "") or "Bayesian" in h["snippet"] for h in hits)

    # 3. Cross-library search via MCP finds the same content.
    lib_hits = search_library_content_impl(lib.session, query="Bayesian")
    assert len(lib_hits) >= 1
    assert lib_hits[0]["book_id"] == book.id
