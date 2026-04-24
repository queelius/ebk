"""Arkiv export for book-memex libraries.

Output can be a directory, a ``.zip`` archive, or a ``.tar.gz`` tarball;
the choice is inferred from the output path's extension. All three layouts
contain the same files:

- ``records.jsonl`` : one JSON line per active book / marginalia / reading
- ``schema.yaml``   : archive self-description + per-key metadata stats
- ``README.md``     : arkiv ECHO frontmatter + human-readable explanation

Record URI scheme::

    book-memex://book/<unique_id>
    book-memex://marginalia/<uuid>
    book-memex://reading/<uuid>

Only non-archived rows (``archived_at IS NULL``) are emitted.

Compression choice prioritises longevity: ``.zip`` and ``.tar.gz`` are
both ubiquitous on every OS (30+ years of universal tooling). Modern
compressors like ``zstd`` are deliberately avoided so the bundle still
opens in 2050.
"""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from datetime import date, datetime, timezone
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
            "description": (
                "Reader's note, highlight, or observation. May span zero, "
                "one, or multiple books."
            ),
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
                "scope": (
                    "Derived scope: 'highlight', 'book_note', "
                    "'collection_note', or 'cross_book_note'."
                ),
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
                "start_anchor": (
                    "Opaque position anchor at session start (cfi, offset, etc)."
                ),
                "end_anchor": "Opaque position anchor at session end.",
                "pages_read": "Integer pages read during session.",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Bundle format detection
# ---------------------------------------------------------------------------


def _detect_compression(path: str | Path) -> str:
    """Infer output format from *path*'s extension.

    Returns one of ``"zip"``, ``"tar.gz"``, ``"dir"``.
    """
    lower = str(path).lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar.gz"
    return "dir"


def _iso(dt: datetime | None) -> str | None:
    """Return ISO 8601 string or None."""
    if dt is None:
        return None
    return dt.isoformat()


# ---------------------------------------------------------------------------
# File serialisation helpers (shared by all three bundle formats)
# ---------------------------------------------------------------------------


def _records_to_jsonl_bytes(records: Iterable[Dict[str, Any]]) -> tuple[bytes, Dict[str, int]]:
    """Serialise records to JSONL bytes and return live per-kind counts."""
    counts: Dict[str, int] = {"book": 0, "marginalia": 0, "reading": 0}
    buf = io.StringIO()
    for rec in records:
        buf.write(json.dumps(rec, ensure_ascii=False) + "\n")
        kind = rec.get("kind")
        if kind in counts:
            counts[kind] += 1
    return buf.getvalue().encode("utf-8"), counts


def _schema_yaml_bytes(counts: Dict[str, int]) -> bytes:
    """Render schema.yaml with field docs + live counts."""
    doc = {
        "scheme": SCHEMA["scheme"],
        "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "counts": counts,
        "kinds": SCHEMA["kinds"],
    }
    buf = io.StringIO()
    buf.write("# Auto-generated by book-memex. Edit freely.\n")
    yaml.safe_dump(doc, buf, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return buf.getvalue().encode("utf-8")


def _readme_bytes(counts: Dict[str, int]) -> bytes:
    """Render README.md with ECHO frontmatter + usage notes."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    try:
        version = _pkg_version("book-memex")
    except PackageNotFoundError:
        version = "unknown"

    today = date.today().isoformat()
    n_book = counts.get("book", 0)
    n_marg = counts.get("marginalia", 0)
    n_read = counts.get("reading", 0)
    lines = [
        "---",
        "name: book-memex archive",
        (
            f'description: "{n_book} books + {n_marg} marginalia + '
            f'{n_read} reading sessions exported from book-memex"'
        ),
        f"datetime: {today}",
        f"generator: book-memex {version}",
        "contents:",
        "  - path: records.jsonl",
        "    description: Book, marginalia, and reading session records (arkiv JSONL)",
        "  - path: schema.yaml",
        "    description: Record schema + per-kind counts",
        "---",
        "",
        "# book-memex Archive",
        "",
        (
            f"This archive contains {n_book} book(s), {n_marg} marginalia, "
            f"and {n_read} reading session(s)"
        ),
        "exported from book-memex in [arkiv](https://github.com/queelius/arkiv) format.",
        "",
        "Each line in `records.jsonl` is one record. Records are typed by `kind`:",
        "",
        "- `book`: library metadata for one book.",
        "- `marginalia`: a free-form note (highlight or observation), "
        "potentially attached to zero, one, or multiple books.",
        "- `reading`: a reading session for a book.",
        "",
        "URIs follow the cross-archive `book-memex://` scheme and stay stable",
        "across re-imports, so marginalia and reading sessions survive their",
        "parent book being re-imported or round-tripped through another archive.",
        "",
        "## Importing back into book-memex",
        "",
        "```bash",
        "# Insert-or-ignore on unique_id + uuid; safe for re-imports.",
        "book-memex import-arkiv <this bundle>",
        "",
        "# Or with explicit --merge semantics (same effect today; reserved",
        "# for a future stricter-insert mode).",
        "book-memex import-arkiv <this bundle> --merge",
        "```",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _write_file(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _write_zip(
    path: Path, jsonl: bytes, schema_yaml: bytes, readme: bytes
) -> None:
    """Write the three bundle files into a single .zip archive."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("records.jsonl", jsonl)
        zf.writestr("schema.yaml", schema_yaml)
        zf.writestr("README.md", readme)


def _write_tar_gz(
    path: Path, jsonl: bytes, schema_yaml: bytes, readme: bytes
) -> None:
    """Write the three bundle files into a single .tar.gz archive."""
    with tarfile.open(path, "w:gz") as tf:
        for name, data in (
            ("records.jsonl", jsonl),
            ("schema.yaml", schema_yaml),
            ("README.md", readme),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class ArkivExporter:
    """Emit JSONL records + schema.yaml + README.md for an open Library.

    Usage::

        exporter = ArkivExporter(lib)
        exporter.run(out_path)

    The output path's extension drives the bundle format:

    - ``path``                -> directory
    - ``path.zip``            -> single zip file
    - ``path.tar.gz``/``.tgz`` -> single gzip-compressed tarball
    """

    def __init__(self, library) -> None:
        # Avoid a circular import by typing `library` loosely.
        self.library = library
        self.session: Session = library.session

    # -- public API ---------------------------------------------------

    def run(self, out_path: Path) -> Dict[str, Any]:
        """Write the arkiv bundle to ``out_path``.

        Returns a dict with bundle metadata and per-kind counts. For a
        directory bundle, ``records_path`` and ``schema_path`` are set to
        the files inside that directory; for archive bundles both point
        at the archive file itself.
        """
        out_path = Path(out_path)
        fmt = _detect_compression(out_path)

        # Build records once; serialise into the chosen format.
        records = list(self._iter_records())
        jsonl_bytes, counts = _records_to_jsonl_bytes(records)
        schema_bytes = _schema_yaml_bytes(counts)
        readme_bytes = _readme_bytes(counts)

        if fmt == "zip":
            out_path.parent.mkdir(parents=True, exist_ok=True)
            _write_zip(out_path, jsonl_bytes, schema_bytes, readme_bytes)
            records_path = schema_path = str(out_path)
        elif fmt == "tar.gz":
            out_path.parent.mkdir(parents=True, exist_ok=True)
            _write_tar_gz(out_path, jsonl_bytes, schema_bytes, readme_bytes)
            records_path = schema_path = str(out_path)
        else:
            out_path.mkdir(parents=True, exist_ok=True)
            _write_file(out_path / "records.jsonl", jsonl_bytes)
            _write_file(out_path / "schema.yaml", schema_bytes)
            _write_file(out_path / "README.md", readme_bytes)
            records_path = str(out_path / "records.jsonl")
            schema_path = str(out_path / "schema.yaml")

        return {
            "path": str(out_path),
            "format": fmt,
            "records_path": records_path,
            "schema_path": schema_path,
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
