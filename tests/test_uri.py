"""Unit tests for book_memex.core.uri."""
import pytest

from book_memex.core.uri import (
    build_book_uri,
    build_marginalia_uri,
    build_reading_uri,
    parse_uri,
    ParsedUri,
    InvalidUriError,
    SCHEME,
)


class TestBuilders:
    def test_book_uri(self):
        assert build_book_uri("abc123") == "book-memex://book/abc123"

    def test_book_uri_preserves_isbn_prefix(self):
        assert build_book_uri("isbn_9780123456789") == "book-memex://book/isbn_9780123456789"

    def test_marginalia_uri(self):
        assert build_marginalia_uri("a1b2c3") == "book-memex://marginalia/a1b2c3"

    def test_reading_uri(self):
        assert build_reading_uri("deadbeef") == "book-memex://reading/deadbeef"

    def test_builder_rejects_empty_id(self):
        with pytest.raises(ValueError):
            build_book_uri("")


class TestParser:
    def test_parse_book_uri(self):
        result = parse_uri("book-memex://book/abc123")
        assert result == ParsedUri(scheme=SCHEME, kind="book", id="abc123", fragment=None)

    def test_parse_marginalia_uri(self):
        result = parse_uri("book-memex://marginalia/xyz")
        assert result.kind == "marginalia"
        assert result.id == "xyz"

    def test_parse_with_fragment_epubcfi(self):
        uri = "book-memex://book/abc#epubcfi(/6/4[chap03]!/4)"
        result = parse_uri(uri)
        assert result.id == "abc"
        assert result.fragment == "epubcfi(/6/4[chap03]!/4)"

    def test_parse_with_fragment_page(self):
        result = parse_uri("book-memex://book/abc#page=47")
        assert result.fragment == "page=47"

    def test_parse_rejects_wrong_scheme(self):
        with pytest.raises(InvalidUriError):
            parse_uri("llm-memex://conversation/abc")

    def test_parse_rejects_malformed(self):
        with pytest.raises(InvalidUriError):
            parse_uri("not-a-uri")

    def test_parse_rejects_empty_id(self):
        with pytest.raises(InvalidUriError):
            parse_uri("book-memex://book/")

    def test_parse_rejects_unknown_kind(self):
        with pytest.raises(InvalidUriError):
            parse_uri("book-memex://trail/abc")


class TestRoundtrip:
    def test_book_uri_roundtrip(self):
        uri = build_book_uri("xyz")
        parsed = parse_uri(uri)
        assert parsed.kind == "book"
        assert parsed.id == "xyz"

    def test_marginalia_uri_roundtrip(self):
        uri = build_marginalia_uri("uuid-value")
        parsed = parse_uri(uri)
        assert parsed.kind == "marginalia"
        assert parsed.id == "uuid-value"
