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


# --- EPUB extractor tests (Task 6) ---


def test_epub_extractor_yields_one_segment_per_chapter(sample_epub):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("epub")
    segments = list(ex.extract(sample_epub))
    # spine has "nav" + 3 chapters; extractor skips the nav.
    assert len(segments) == 3
    assert [s.segment_index for s in segments] == [0, 1, 2]
    assert [s.segment_type for s in segments] == ["chapter"] * 3
    assert "Intro" in segments[0].title
    assert "Bayesian" in segments[1].title
    assert "quick brown fox" in segments[0].text
    assert "Bayesian" in segments[1].text or "Priors" in segments[1].text


def test_epub_extractor_produces_cfi_anchor(sample_epub):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("epub")
    segments = list(ex.extract(sample_epub))
    for s in segments:
        assert "cfi" in s.anchor
        assert s.anchor["cfi"].startswith("epubcfi(")


def test_epub_extractor_status_ok(sample_epub):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("epub")
    for s in ex.extract(sample_epub):
        assert s.extraction_status == "ok"


# --- PDF extractor tests (Task 7) ---


def test_pdf_extractor_yields_one_segment_per_page(sample_pdf):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("pdf")
    segments = list(ex.extract(sample_pdf))
    assert len(segments) == 3
    assert [s.segment_type for s in segments] == ["page"] * 3
    assert [s.segment_index for s in segments] == [0, 1, 2]


def test_pdf_extractor_page_anchors(sample_pdf):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("pdf")
    segments = list(ex.extract(sample_pdf))
    for i, s in enumerate(segments):
        assert s.anchor == {"page": i + 1}  # 1-based


def test_pdf_extractor_captures_text(sample_pdf):
    from book_memex.services.content_extraction import get_extractor

    ex = get_extractor("pdf")
    segments = list(ex.extract(sample_pdf))
    joined = " ".join(s.text for s in segments)
    assert "quick brown fox" in joined
    assert "Bayesian" in joined


def test_pdf_extractor_flags_no_text_layer(tmp_path):
    """A PDF with no text layer emits segments with extraction_status='no_text_layer'."""
    from pypdf import PdfWriter
    from book_memex.services.content_extraction import get_extractor

    # Build a 2-page PDF with truly blank pages (no text operators).
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    out = tmp_path / "blank.pdf"
    with open(out, "wb") as f:
        writer.write(f)

    ex = get_extractor("pdf")
    segments = list(ex.extract(out))
    assert len(segments) == 2
    assert all(s.extraction_status == "no_text_layer" for s in segments)
    assert all(s.text == "" for s in segments)
