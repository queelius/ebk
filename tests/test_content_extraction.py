"""Tests for the extractor interface and dispatch."""
import pytest
from pathlib import Path

from book_memex.services.content_extraction import (
    Segment, Extractor, get_extractor, SUPPORTED_FORMATS,
)


def test_segment_dataclass_is_frozen_enough():
    """Segment must carry the fields documented in the spec."""
    s = Segment(
        segment_type="chapter",
        segment_index=3,
        title="The Third Chapter",
        anchor={"cfi": "epubcfi(/6/8[chap03]!/4)"},
        text="chapter body",
        start_page=50,
        end_page=75,
        extraction_status="ok",
    )
    assert s.segment_type == "chapter"
    assert s.segment_index == 3
    assert s.title == "The Third Chapter"
    assert s.anchor == {"cfi": "epubcfi(/6/8[chap03]!/4)"}
    assert s.text == "chapter body"
    assert s.start_page == 50
    assert s.end_page == 75
    assert s.extraction_status == "ok"


def test_supported_formats():
    assert "epub" in SUPPORTED_FORMATS
    assert "pdf" in SUPPORTED_FORMATS
    assert "txt" in SUPPORTED_FORMATS


def test_get_extractor_raises_on_unknown_format():
    with pytest.raises(ValueError):
        get_extractor("wingdings")


def test_get_extractor_returns_matching_extractor():
    ex = get_extractor("epub")
    assert ex.version.startswith("epub-")
    assert ex.supports("epub") is True
    assert ex.supports("pdf") is False
