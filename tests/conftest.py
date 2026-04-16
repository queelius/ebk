"""Shared fixtures for book-memex tests."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_epub(tmp_path):
    """A 3-chapter EPUB constructed in-memory for extractor tests."""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("test-epub-phase2")
    book.set_title("Phase 2 Sample")
    book.set_language("en")
    book.add_author("Test Author")

    chapters = []
    for i, (title, body) in enumerate([
        ("Intro", "<h1>Intro</h1><p>The quick brown fox jumps.</p>"),
        ("Bayesian Primer", "<h1>Bayesian Primer</h1><p>Priors meet likelihoods.</p>"),
        ("Conclusion", "<h1>Conclusion</h1><p>Thus concludes the sample.</p>"),
    ]):
        c = epub.EpubHtml(
            title=title,
            file_name=f"chap{i+1}.xhtml",
            lang="en",
        )
        c.set_content(
            f'<html xmlns="http://www.w3.org/1999/xhtml">'
            f"<head><title>{title}</title></head>"
            f"<body>{body}</body></html>"
        )
        c.id = f"chap{i+1}"
        book.add_item(c)
        chapters.append(c)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    out = tmp_path / "sample.epub"
    epub.write_epub(str(out), book)
    return out


@pytest.fixture
def sample_pdf(tmp_path):
    """A 3-page PDF constructed with reportlab for extractor tests."""
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed; PDF fixture unavailable")

    out = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(out))
    for body in [
        "Page one quick brown fox.",
        "Page two Bayesian inference.",
        "Page three the conclusion.",
    ]:
        c.drawString(72, 720, body)
        c.showPage()
    c.save()
    return out
