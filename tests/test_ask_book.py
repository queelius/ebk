"""Tests for ask_book: FTS5 retrieval + LLM answer."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.services.ask_book import ask_book, AskBookResult


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


def _mock_llm_success(prompt: str, **kwargs) -> str:
    """Return a canned answer that references the Bayesian chapter segment."""
    return (
        "Bayesian inference is explained in Chapter 2. "
        "See [book-memex://book/abc#epubcfi(/6/4[chap2]!/4)]."
    )


def _mock_llm_raise(prompt: str, **kwargs) -> str:
    raise RuntimeError("llm unavailable")


def test_ask_book_returns_answer_with_citations(lib_indexed):
    lib, book = lib_indexed
    result = ask_book(
        lib.session, book_id=book.id, question="Bayesian",
        llm=_mock_llm_success,
    )
    assert isinstance(result, AskBookResult)
    assert result.answer is not None
    assert len(result.segments_used) >= 1
    # Each used segment has a URI fragment.
    for seg in result.segments_used:
        assert "fragment" in seg
    # Citations parsed out of the LLM response.
    assert any("epubcfi" in c.get("fragment", "") for c in result.citations)


def test_ask_book_no_matches(lib_indexed):
    lib, book = lib_indexed
    result = ask_book(
        lib.session, book_id=book.id, question="zxcvbnm_never_present",
        llm=_mock_llm_success,
    )
    assert result.answer is None
    assert result.segments_used == []
    assert result.message is not None
    assert "no matching" in result.message.lower()


def test_ask_book_llm_failure_surfaces(lib_indexed):
    lib, book = lib_indexed
    result = ask_book(
        lib.session, book_id=book.id, question="Bayesian",
        llm=_mock_llm_raise,
    )
    assert result.answer is None
    assert result.message is not None
    assert "llm" in result.message.lower()


def test_ask_book_requires_configured_llm_by_default(lib_indexed):
    """Without a llm callable passed in, ask_book should raise or return a clear message."""
    lib, book = lib_indexed
    result = ask_book(
        lib.session, book_id=book.id, question="Bayesian", llm=None,
    )
    assert result.answer is None
    assert result.message is not None
    assert "llm" in result.message.lower() or "configure" in result.message.lower()
