"""Book-memex URI builder and parser.

Public URI kinds:
    book-memex://book/<unique_id>
    book-memex://marginalia/<uuid>
    book-memex://reading/<uuid>

Fragments (positions inside a Book):
    book-memex://book/<unique_id>#epubcfi(...)
    book-memex://book/<unique_id>#page=<n>
    book-memex://book/<unique_id>#cfi-range=<start>/to/<end>
    book-memex://book/<unique_id>#text-match=<encoded>

The fragment is anything after the first `#` and is returned verbatim.
This module intentionally has no SQLAlchemy dependency so it can be
used by both archive internals and external consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SCHEME = "book-memex"
KINDS = frozenset({"book", "marginalia", "reading"})


class InvalidUriError(ValueError):
    """Raised when a URI string does not match the book-memex scheme."""


@dataclass(frozen=True)
class ParsedUri:
    scheme: str
    kind: str
    id: str
    fragment: Optional[str]


def build_book_uri(unique_id: str) -> str:
    return _build("book", unique_id)


def build_marginalia_uri(uuid: str) -> str:
    return _build("marginalia", uuid)


def build_reading_uri(uuid: str) -> str:
    return _build("reading", uuid)


def _build(kind: str, ident: str) -> str:
    if not ident:
        raise ValueError(f"cannot build {kind} URI from empty id")
    if kind not in KINDS:
        raise ValueError(f"unknown URI kind: {kind}")
    return f"{SCHEME}://{kind}/{ident}"


def parse_uri(uri: str) -> ParsedUri:
    """Parse a book-memex URI into its components.

    Raises InvalidUriError on any structural problem.
    """
    if not isinstance(uri, str) or "://" not in uri:
        raise InvalidUriError(f"not a URI: {uri!r}")

    scheme, _, rest = uri.partition("://")
    if scheme != SCHEME:
        raise InvalidUriError(
            f"expected scheme {SCHEME!r}, got {scheme!r} in {uri!r}"
        )

    kind, _, tail = rest.partition("/")
    if kind not in KINDS:
        raise InvalidUriError(f"unknown kind {kind!r} in {uri!r}")

    ident, sep, fragment = tail.partition("#")
    if not ident:
        raise InvalidUriError(f"empty id in {uri!r}")

    return ParsedUri(
        scheme=scheme,
        kind=kind,
        id=ident,
        fragment=fragment if sep else None,
    )


def build_book_fragment_uri(unique_id: str, fragment: str) -> str:
    """Build a book URI with a fragment denoting a position or range."""
    base = build_book_uri(unique_id)
    if not fragment:
        return base
    return f"{base}#{fragment}"
