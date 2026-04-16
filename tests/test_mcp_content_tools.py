"""Tests for MCP content-search tools."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    search_book_content_impl,
    search_library_content_impl,
    get_segment_impl,
    get_segments_impl,
)


@pytest.fixture
def lib_indexed(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "a.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(dest, metadata={"title": "A", "creators": ["X"]}, extract_text=True)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_search_book_content(lib_indexed):
    lib, book = lib_indexed
    hits = search_book_content_impl(lib.session, book_id=book.id, query="Bayesian")
    assert len(hits) >= 1
    assert hits[0]["segment_type"] == "chapter"
    assert "fragment" in hits[0]


def test_search_library_content(lib_indexed):
    lib, book = lib_indexed
    hits = search_library_content_impl(lib.session, query="quick brown fox")
    assert len(hits) >= 1
    assert hits[0]["book_uri"].startswith("book-memex://book/")


def test_get_segment_by_index(lib_indexed):
    lib, book = lib_indexed
    seg = get_segment_impl(
        lib.session, book_id=book.id, segment_type="chapter", segment_index=0,
    )
    assert seg["segment_index"] == 0
    assert "text" in seg
    assert "Intro" in (seg.get("title") or "") or "Intro" in seg.get("text", "")


def test_get_segments_paginated(lib_indexed):
    lib, book = lib_indexed
    segs = get_segments_impl(lib.session, book_id=book.id, limit=2, offset=0)
    assert len(segs) == 2
    assert [s["segment_index"] for s in segs] == [0, 1]
    more = get_segments_impl(lib.session, book_id=book.id, limit=2, offset=2)
    assert len(more) == 1
    assert more[0]["segment_index"] == 2


def test_search_rejects_empty_query(lib_indexed):
    lib, book = lib_indexed
    with pytest.raises(ValueError):
        search_book_content_impl(lib.session, book_id=book.id, query="")
