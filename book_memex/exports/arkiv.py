"""Arkiv export format for book-memex libraries.

The arkiv format is a JSONL record stream paired with a YAML schema
descriptor, designed for LLM / MCP consumption and cross-archive
interoperability. Each record has a ``kind`` field and a URI.

Output layout::

    <out>/
      records.jsonl  -- one record per line (book, marginalia, reading)
      schema.yaml    -- field descriptors per kind

Only non-archived rows (``archived_at IS NULL``) are emitted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator

import yaml
from sqlalchemy.orm import Session

from ..db.models import Book, Marginalia, ReadingSession


__all__ = ["export_arkiv", "ArkivExporter", "SCHEMA"]


# Schema describing the JSONL record kinds emitted by this exporter.
# Keeping this as module-level data lets callers introspect without
# running the export.
SCHEMA: Dict[str, Any] = {
    "scheme": "book-memex",
    "kinds": {
        "book": {
            "description": "A book in the library.",
            "uri": "book-memex://book/<unique_id>",
            "fields": {
                "kind": "Always 'book'.",
                "uri": "Canonical book-memex URI.",
                "unique_id": "Hash-based durable ID (32 hex chars).",
                "title": "Book title.",
                "subtitle": "Book subtitle, if any.",
                "authors": "List of author names.",
                "language": "ISO 639-1 language code.",
                "publisher": "Publisher name.",
                "publication_date": "Year/date string (flexible format).",
                "description": "Description / abstract.",
                "subjects": "List of subject names.",
                "series": "Series name, if any.",
                "series_index": "Position in series (float).",
                "identifiers": "Map of scheme -> value (e.g. isbn).",
                "tags": "List of hierarchical tag paths.",
                "created_at": "ISO 8601 timestamp.",
                "updated_at": "ISO 8601 timestamp.",
            },
        },
        "marginalia": {
            "description": "Reader's note, highlight, or observation. May span zero, one, or multiple books.",
            "uri": "book-memex://marginalia/<uuid>",
            "fields": {
                "kind": "Always 'marginalia'.",
                "uri": "Canonical book-memex URI.",
                "uuid": "Durable UUID (hex, no dashes).",
                "content": "The reader's note (markdown).",
                "highlighted_text": "The passage being annotated.",
                "page_number": "Page number (integer, nullable).",
                "position": "Position metadata object (cfi, char_offset, x/y).",
                "category": "User-defined category.",
                "color": "Hex color string (e.g. '#ffff00').",
                "pinned": "Whether the note is pinned.",
                "scope": "Derived scope: 'highlight', 'book_note', 'collection_note', or 'cross_book_note'.",
                "book_uris": "List of book URIs this entry relates to.",
                "created_at": "ISO 8601 timestamp.",
                "updated_at": "ISO 8601 timestamp.",
            },
        },
        "reading": {
            "description": "A reading session for a book.",
            "uri": "book-memex://reading/<uuid>",
            "fields": {
                "kind": "Always 'reading'.",
                "uri": "Canonical book-memex URI.",
                "uuid": "Durable UUID (hex, no dashes).",
                "book_uri": "URI of the book being read.",
                "start_time": "ISO 8601 timestamp.",
                "end_time": "ISO 8601 timestamp, nullable (null = open session).",
                "start_anchor": "Opaque position anchor at session start (cfi, offset, etc).",
                "end_anchor": "Opaque position anchor at session end.",
                "pages_read": "Integer pages read during session.",
            },
        },
    },
}


def _iso(dt: datetime | None) -> str | None:
    """Return ISO 8601 string or None."""
    if dt is None:
        return None
    return dt.isoformat()


class ArkivExporter:
    """Emit JSONL records + schema.yaml for an open Library.

    Usage::

        exporter = ArkivExporter(lib)
        exporter.run(out_path)
    """

    def __init__(self, library) -> None:
        # Avoid a circular import by typing `library` loosely.
        self.library = library
        self.session: Session = library.session

    # -- public API ---------------------------------------------------

    def run(self, out_path: Path) -> Dict[str, Any]:
        """Write records.jsonl and schema.yaml into ``out_path``.

        Returns a dict with counts per kind.
        """
        out = Path(out_path)
        out.mkdir(parents=True, exist_ok=True)

        counts = {"book": 0, "marginalia": 0, "reading": 0}
        records_path = out / "records.jsonl"
        with open(records_path, "w", encoding="utf-8") as fp:
            for rec in self._iter_records():
                fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kind = rec.get("kind")
                if kind in counts:
                    counts[kind] += 1

        schema_path = out / "schema.yaml"
        with open(schema_path, "w", encoding="utf-8") as fp:
            yaml.safe_dump(
                {
                    "scheme": SCHEMA["scheme"],
                    "exported_at": datetime.now(timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat(),
                    "kinds": SCHEMA["kinds"],
                },
                fp,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )

        return {
            "records_path": str(records_path),
            "schema_path": str(schema_path),
            "counts": counts,
        }

    # -- record generation -------------------------------------------

    def _iter_records(self) -> Iterator[Dict[str, Any]]:
        yield from self._iter_books()
        yield from self._iter_marginalia()
        yield from self._iter_reading_sessions()

    def _iter_books(self) -> Iterable[Dict[str, Any]]:
        q = (
            self.session.query(Book)
            .filter(Book.archived_at.is_(None))
            .order_by(Book.id.asc())
        )
        for book in q:
            yield {
                "kind": "book",
                "uri": book.uri,
                "unique_id": book.unique_id,
                "title": book.title,
                "subtitle": book.subtitle,
                "authors": [a.name for a in book.authors],
                "language": book.language,
                "publisher": book.publisher,
                "publication_date": book.publication_date,
                "description": book.description,
                "subjects": [s.name for s in book.subjects],
                "series": book.series,
                "series_index": book.series_index,
                "identifiers": {
                    i.scheme: i.value for i in book.identifiers
                },
                "tags": [t.full_path for t in book.tags] if book.tags else [],
                "created_at": _iso(book.created_at),
                "updated_at": _iso(book.updated_at),
            }

    def _iter_marginalia(self) -> Iterable[Dict[str, Any]]:
        q = (
            self.session.query(Marginalia)
            .filter(Marginalia.archived_at.is_(None))
            .order_by(Marginalia.id.asc())
        )
        for m in q:
            yield {
                "kind": "marginalia",
                "uri": m.uri,
                "uuid": m.uuid,
                "content": m.content,
                "highlighted_text": m.highlighted_text,
                "page_number": m.page_number,
                "position": m.position,
                "category": m.category,
                "color": m.color,
                "pinned": bool(m.pinned),
                "scope": m.scope,
                "book_uris": [b.uri for b in m.books],
                "created_at": _iso(m.created_at),
                "updated_at": _iso(m.updated_at),
            }

    def _iter_reading_sessions(self) -> Iterable[Dict[str, Any]]:
        q = (
            self.session.query(ReadingSession)
            .filter(ReadingSession.archived_at.is_(None))
            .order_by(ReadingSession.id.asc())
        )
        for rs in q:
            yield {
                "kind": "reading",
                "uri": rs.uri,
                "uuid": rs.uuid,
                "book_uri": rs.book.uri if rs.book else None,
                "start_time": _iso(rs.start_time),
                "end_time": _iso(rs.end_time),
                "start_anchor": rs.start_anchor,
                "end_anchor": rs.end_anchor,
                "pages_read": rs.pages_read,
            }


def export_arkiv(library, out_path: Path) -> Dict[str, Any]:
    """Convenience wrapper around :class:`ArkivExporter`."""
    return ArkivExporter(library).run(out_path)
