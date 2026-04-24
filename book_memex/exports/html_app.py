"""Single-file HTML SPA export for book-memex (C6 workspace contract).

Produces one self-contained ``.html`` file with:

- Inlined sql-wasm.js (vendored; no CDN).
- Base64-encoded sql-wasm.wasm (loaded via ``initSqlJs({wasmBinary:...})``).
- Gzipped + base64-encoded SQLite database, decompressed in-browser via
  ``DecompressionStream('gzip')``.

The archive is genuinely portable: one file, opens anywhere, no network
requests, no CDN dependency, no authentication on the author's behalf.

The shipped DB is denormalized for the browser:

- ``books``       one row per book; authors / subjects / tags / identifiers
                  are JSON-column denormalizations (no join tables in the
                  client) so LIKE-based filtering works without FTS5.
- ``marginalia``  notes with a ``book_unique_ids_json`` JSON array for
                  client-side filter-by-book.

FTS5 virtual tables are *not* shipped: the vendored sql.js build does
not compile with FTS5. Client-side search uses LIKE across the JSON
columns and description; adequate for a single-user library.

Hash routes:

- ``#/``                  home (popular tags + top authors + recent books)
- ``#/book/<unique_id>``  book detail + attached marginalia
- ``#/tag/<name>``        books with this tag
- ``#/subject/<name>``    books with this subject
- ``#/author/<name>``     books by this author
- ``#/search/<q>``        LIKE across title/subtitle/description/JSON cols
- ``#/marginalia``        all marginalia across the library

Sibling to the older ``html_library.py`` static-JSON viewer. This file
is the workspace-contract-compliant exporter; ``html_library.py``
remains for users who prefer its static model.
"""

from __future__ import annotations

import base64
import gzip
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List


_VENDORED_DIR = Path(__file__).parent / "vendored"
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "html_app.html"
# gzip level 6 is the sweet spot: near-maximum ratio, modest CPU cost.
_DB_GZIP_LEVEL = 6


# ---------------------------------------------------------------------------
# Export DB builder
# ---------------------------------------------------------------------------


def _build_export_db(library) -> bytes:
    """Build an in-memory SQLite DB of the library, return raw bytes.

    Denormalized schema (no join tables; JSON array columns for the
    browser's LIKE-based filtering).
    """
    from ..db.models import Book, Marginalia, ReadingSession

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=DELETE")
    cur.executescript(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            unique_id TEXT UNIQUE,
            title TEXT NOT NULL,
            subtitle TEXT,
            authors_json TEXT,
            subjects_json TEXT,
            tags_json TEXT,
            identifiers_json TEXT,
            language TEXT,
            publisher TEXT,
            publication_date TEXT,
            description TEXT,
            series TEXT,
            series_index REAL,
            page_count INTEGER,
            created_at TEXT,
            updated_at TEXT,
            archived_at TEXT
        );
        CREATE TABLE marginalia (
            uuid TEXT PRIMARY KEY,
            content TEXT,
            highlighted_text TEXT,
            page_number INTEGER,
            color TEXT,
            pinned INTEGER,
            scope TEXT,
            book_unique_ids_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            archived_at TEXT
        );
        CREATE TABLE reading_sessions (
            uuid TEXT PRIMARY KEY,
            book_unique_id TEXT,
            start_time TEXT,
            end_time TEXT,
            pages_read INTEGER,
            created_at TEXT,
            archived_at TEXT
        );
        CREATE INDEX idx_books_unique_id ON books(unique_id);
        CREATE INDEX idx_marginalia_created ON marginalia(created_at);
        """
    )

    session = library.session

    def _iso(dt) -> str | None:
        return dt.isoformat() if dt else None

    # Books
    for book in session.query(Book).order_by(Book.id.asc()):
        authors = [a.name for a in book.authors]
        subjects = [s.name for s in book.subjects]
        tags = [t.full_path for t in book.tags] if book.tags else []
        identifiers = {i.scheme: i.value for i in book.identifiers}

        cur.execute(
            "INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                book.id,
                book.unique_id,
                book.title,
                book.subtitle,
                json.dumps(authors, ensure_ascii=False) if authors else None,
                json.dumps(subjects, ensure_ascii=False) if subjects else None,
                json.dumps(tags, ensure_ascii=False) if tags else None,
                json.dumps(identifiers, ensure_ascii=False) if identifiers else None,
                book.language,
                book.publisher,
                book.publication_date,
                book.description,
                book.series,
                book.series_index,
                book.page_count,
                _iso(book.created_at),
                _iso(book.updated_at),
                _iso(book.archived_at),
            ),
        )

    # Marginalia
    for m in session.query(Marginalia).order_by(Marginalia.id.asc()):
        book_uids = [b.unique_id for b in m.books]
        cur.execute(
            "INSERT INTO marginalia VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                m.uuid,
                m.content,
                m.highlighted_text,
                m.page_number,
                m.color,
                1 if m.pinned else 0,
                m.scope,
                json.dumps(book_uids, ensure_ascii=False) if book_uids else None,
                _iso(m.created_at),
                _iso(m.updated_at),
                _iso(m.archived_at),
            ),
        )

    # Reading sessions
    for rs in session.query(ReadingSession).order_by(ReadingSession.id.asc()):
        book_uid = rs.book.unique_id if rs.book else None
        cur.execute(
            "INSERT INTO reading_sessions VALUES (?,?,?,?,?,?,?)",
            (
                rs.uuid,
                book_uid,
                _iso(rs.start_time),
                _iso(rs.end_time),
                rs.pages_read,
                _iso(rs.start_time),
                _iso(rs.archived_at),
            ),
        )

    conn.commit()
    # VACUUM requires no open cursors or pending statements.
    cur.close()
    conn.execute("VACUUM")
    data: bytes = conn.serialize()
    conn.close()
    return data


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


def _read_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _read_vendor(name: str) -> bytes:
    return (_VENDORED_DIR / name).read_bytes()


def export_html_app(library, out_path: Path) -> Dict[str, Any]:
    """Export the library as a self-contained single-file HTML SPA.

    Parameters
    ----------
    library:
        An open :class:`book_memex.library_db.Library` instance.
    out_path:
        Target file path. ``.html`` is auto-appended if missing.

    Returns
    -------
    dict
        ``{"path", "html_bytes", "original_db_bytes", "embedded_db_bytes"}``.
    """
    out = Path(out_path)
    if not out.suffix:
        out = out.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)

    db_bytes = _build_export_db(library)
    db_gz = gzip.compress(db_bytes, compresslevel=_DB_GZIP_LEVEL)
    db_b64 = base64.b64encode(db_gz).decode("ascii")

    sqljs_js = _read_vendor("sql-wasm.js").decode("utf-8")
    wasm_b64 = base64.b64encode(_read_vendor("sql-wasm.wasm")).decode("ascii")

    # Defensive: neutralise any literal "</script>" in the sql.js body so
    # it can't terminate the wrapping <script> tag in the HTML. Current
    # vendored build contains no such sequence but this costs one
    # replace().
    sqljs_safe = sqljs_js.replace("</script>", "<\\/script>")

    html = (
        _read_template()
        .replace("__SQLJS_INLINE__", sqljs_safe)
        .replace("__WASM_BASE64__", wasm_b64)
        .replace("__DB_BASE64_GZ__", db_b64)
    )

    out.write_text(html, encoding="utf-8")

    return {
        "path": str(out),
        "format": "html-app",
        "html_bytes": out.stat().st_size,
        "original_db_bytes": len(db_bytes),
        "embedded_db_bytes": len(db_gz),
    }
