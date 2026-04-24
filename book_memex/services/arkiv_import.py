"""Import an arkiv bundle back into book-memex.

Bundles emitted by :mod:`book_memex.exports.arkiv` (or any other tool
following the arkiv spec, within reason) are read, classified by record
kind, and inserted into the DB.

Supported input layouts (all auto-detected):

- directory with ``records.jsonl``, ``schema.yaml``, and ``README.md``
- ``.zip`` file containing those files
- ``.tar.gz`` / ``.tgz`` file containing those files
- bare ``.jsonl`` file of arkiv records (no schema/README needed)
- ``.jsonl.gz`` file of gzipped arkiv records — the shape an HTML SPA
  would emit for round-tripping marginalia back to the primary DB

This is intentionally forgiving: if ``schema.yaml`` or ``README.md`` is
missing but ``records.jsonl`` is present, we still import. The bundle's
"identity as a book-memex arkiv" is a soft claim; the JSONL records
are what we actually need.

Record kinds handled:

- ``kind == "book"``       : insert or skip-duplicate keyed on unique_id
                             (metadata only; no file payload — files are
                             acquired separately via ``add_book``).
- ``kind == "marginalia"`` : insert or skip-duplicate keyed on uuid.
                             Links to any books that matched unique_id.
- ``kind == "reading"``    : insert or skip-duplicate keyed on uuid;
                             attaches to the matching book if present,
                             otherwise skipped (reading sessions are
                             meaningless without a parent book).
- unknown kinds are ignored.

Round-trip fidelity:

- Books: identified by ``unique_id``. Duplicates are skipped; existing
  rows are left untouched (local tags, personal metadata, etc. survive).
  When a book record carries new authors / subjects / tags / identifiers
  that are not on the existing row, they are merged in.
- Marginalia: identified by uuid. UUID-stable round-trip.
- Reading sessions: identified by uuid. Orphaned sessions (parent book
  missing locally) are skipped with a counter entry so the caller knows.

``--merge`` vs default: duplicate-skipping is the baseline behaviour.
``--merge`` is accepted for CLI parity with the rest of the ``*-memex``
ecosystem and reserves the semantic for a future stricter-add mode.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
import zipfile
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _jsonl_peek_first_record(reader) -> Optional[Dict[str, Any]]:
    """Return the first parsed JSONL record, or None if unparseable/empty."""
    try:
        for line in reader:
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            return rec if isinstance(rec, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return None


_KINDS = ("book", "marginalia", "reading")


def _is_book_memex_arkiv_record(rec: Dict[str, Any]) -> bool:
    """Heuristic: does this record look like one of ours?

    A record from book-memex arkiv export has ``kind`` in
    {"book", "marginalia", "reading"} and either a ``uri`` that starts
    with ``book-memex://`` (strict) or a recognisable shape.
    """
    if not isinstance(rec, dict):
        return False
    kind = rec.get("kind")
    if kind not in _KINDS:
        return False
    uri = rec.get("uri", "")
    if isinstance(uri, str) and uri.startswith("book-memex://"):
        return True
    if kind == "book" and rec.get("unique_id"):
        return True
    if kind == "marginalia" and rec.get("uuid"):
        return True
    if kind == "reading" and rec.get("uuid"):
        return True
    return False


def detect(path: str | Path) -> bool:
    """Return True if *path* looks like an arkiv bundle we can read."""
    p = Path(path)
    if not p.exists():
        return False

    if p.is_dir():
        jsonl = p / "records.jsonl"
        if not jsonl.is_file():
            return False
        with open(jsonl, encoding="utf-8") as f:
            rec = _jsonl_peek_first_record(f)
        return rec is not None and _is_book_memex_arkiv_record(rec)

    lower = str(p).lower()

    if lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(p) as zf:
                if "records.jsonl" not in zf.namelist():
                    return False
                with zf.open("records.jsonl") as f:
                    rec = _jsonl_peek_first_record(f)
            return rec is not None and _is_book_memex_arkiv_record(rec)
        except (zipfile.BadZipFile, KeyError):
            return False

    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        try:
            with tarfile.open(p, "r:gz") as tf:
                try:
                    member = tf.getmember("records.jsonl")
                except KeyError:
                    return False
                extracted = tf.extractfile(member)
                if extracted is None:
                    return False
                rec = _jsonl_peek_first_record(extracted)
            return rec is not None and _is_book_memex_arkiv_record(rec)
        except tarfile.TarError:
            return False

    if lower.endswith(".jsonl.gz"):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                rec = _jsonl_peek_first_record(f)
            return rec is not None and _is_book_memex_arkiv_record(rec)
        except (OSError, gzip.BadGzipFile):
            return False

    if lower.endswith(".jsonl"):
        try:
            with open(p, encoding="utf-8") as f:
                rec = _jsonl_peek_first_record(f)
            return rec is not None and _is_book_memex_arkiv_record(rec)
        except OSError:
            return False

    return False


# ---------------------------------------------------------------------------
# Bundle reading
# ---------------------------------------------------------------------------


def _open_jsonl(path: str | Path) -> Iterator[Dict[str, Any]]:
    """Yield records from the records.jsonl inside a bundle, whatever its shape."""
    p = Path(path)
    if p.is_dir():
        with open(p / "records.jsonl", encoding="utf-8") as f:
            yield from _parse_jsonl_lines(f)
        return

    lower = str(p).lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(p) as zf:
            with zf.open("records.jsonl") as f:
                text = io.TextIOWrapper(f, encoding="utf-8")
                yield from _parse_jsonl_lines(text)
        return
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(p, "r:gz") as tf:
            member = tf.getmember("records.jsonl")
            extracted = tf.extractfile(member)
            if extracted is None:
                return
            text = io.TextIOWrapper(extracted, encoding="utf-8")
            yield from _parse_jsonl_lines(text)
        return
    if lower.endswith(".jsonl.gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            yield from _parse_jsonl_lines(f)
        return
    if lower.endswith(".jsonl"):
        with open(p, encoding="utf-8") as f:
            yield from _parse_jsonl_lines(f)
        return
    raise ValueError(f"unrecognized arkiv bundle: {path!r}")


def _parse_jsonl_lines(reader) -> Iterable[Dict[str, Any]]:
    for line in reader:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    cleaned = ts.replace("Z", "+00:00").split("+")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _unique_id_from_book_uri(uri: Optional[str]) -> Optional[str]:
    """Extract the unique_id from a ``book-memex://book/<id>`` URI."""
    if not uri:
        return None
    prefix = "book-memex://book/"
    if not uri.startswith(prefix):
        return None
    tail = uri[len(prefix):]
    for sep in ("?", "#"):
        idx = tail.find(sep)
        if idx >= 0:
            tail = tail[:idx]
    return tail or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def import_arkiv(
    library,
    path: str | Path,
    *,
    merge: bool = False,
) -> Dict[str, int]:
    """Import an arkiv bundle into *library*.

    Parameters
    ----------
    library:
        An open :class:`book_memex.library_db.Library` instance.
    path:
        Bundle path: directory, ``.zip``, ``.tar.gz``/``.tgz``, bare
        ``.jsonl``, or ``.jsonl.gz``.
    merge:
        Reserved for CLI parity with the rest of the ``*-memex``
        ecosystem. Currently a no-op because the insert path is already
        duplicate-safe.

    Returns
    -------
    dict
        ``{"books_seen": N, "books_added": N, "books_skipped_existing": N,
           "marginalia_seen": N, "marginalia_added": N, "marginalia_skipped_existing": N,
           "reading_seen": N, "reading_added": N, "reading_skipped_existing": N,
           "reading_orphaned": N}``

        ``reading_orphaned`` counts reading-session records whose parent
        book is not present in the local archive (we don't synthesise
        placeholder books for those).
    """
    from sqlalchemy import select

    from ..db.models import (
        Author,
        Book,
        Identifier,
        Marginalia,
        ReadingSession,
        Subject,
        Tag,
    )

    stats = {
        "books_seen": 0,
        "books_added": 0,
        "books_skipped_existing": 0,
        "marginalia_seen": 0,
        "marginalia_added": 0,
        "marginalia_skipped_existing": 0,
        "reading_seen": 0,
        "reading_added": 0,
        "reading_skipped_existing": 0,
        "reading_orphaned": 0,
    }

    records = list(_open_jsonl(path))
    session = library.session

    # Pass 1: books. We buffer unique_id -> Book so subsequent marginalia
    # and reading records can link to them without a second DB round-trip.
    uid_to_book: Dict[str, Book] = {}

    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") != "book":
            continue
        stats["books_seen"] += 1

        unique_id = rec.get("unique_id")
        if not unique_id:
            continue

        existing = session.execute(
            select(Book).where(Book.unique_id == unique_id)
        ).scalar_one_or_none()

        if existing is not None:
            uid_to_book[unique_id] = existing
            # Merge any new authors/subjects/tags/identifiers.
            _merge_book_metadata(session, existing, rec)
            stats["books_skipped_existing"] += 1
            continue

        # Create a bare Book row from metadata only. The arkiv bundle
        # does not carry the file payload; callers acquire files
        # separately via the normal import path and reconcile by
        # unique_id.
        book = Book(
            unique_id=unique_id,
            title=rec.get("title") or "(untitled)",
            subtitle=rec.get("subtitle"),
            language=rec.get("language"),
            publisher=rec.get("publisher"),
            publication_date=rec.get("publication_date"),
            description=rec.get("description"),
            series=rec.get("series"),
            series_index=rec.get("series_index"),
        )
        session.add(book)
        session.flush()  # populate book.id
        _merge_book_metadata(session, book, rec)
        uid_to_book[unique_id] = book
        stats["books_added"] += 1

    session.flush()

    # Pass 2: marginalia.
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") != "marginalia":
            continue
        stats["marginalia_seen"] += 1

        uuid = rec.get("uuid")
        if not uuid:
            continue

        existing_m = session.execute(
            select(Marginalia).where(Marginalia.uuid == uuid)
        ).scalar_one_or_none()
        if existing_m is not None:
            stats["marginalia_skipped_existing"] += 1
            continue

        # Link to any books we can resolve locally.
        book_uris = rec.get("book_uris") or []
        linked_books = []
        for uri in book_uris:
            uid = _unique_id_from_book_uri(uri)
            if not uid:
                continue
            b = uid_to_book.get(uid)
            if b is None:
                # Maybe a book we didn't import this round — look up directly.
                b = session.execute(
                    select(Book).where(Book.unique_id == uid)
                ).scalar_one_or_none()
                if b is not None:
                    uid_to_book[uid] = b
            if b is not None:
                linked_books.append(b)

        m = Marginalia(
            uuid=uuid,
            content=rec.get("content"),
            highlighted_text=rec.get("highlighted_text"),
            page_number=rec.get("page_number"),
            position=rec.get("position"),
            category=rec.get("category"),
            color=rec.get("color"),
            pinned=bool(rec.get("pinned", False)),
        )
        c = _parse_timestamp(rec.get("created_at"))
        u = _parse_timestamp(rec.get("updated_at"))
        if c is not None:
            m.created_at = c
        if u is not None:
            m.updated_at = u
        session.add(m)
        session.flush()
        for b in linked_books:
            m.books.append(b)
        stats["marginalia_added"] += 1

    session.flush()

    # Pass 3: reading sessions.
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") != "reading":
            continue
        stats["reading_seen"] += 1

        uuid = rec.get("uuid")
        if not uuid:
            continue

        existing_rs = session.execute(
            select(ReadingSession).where(ReadingSession.uuid == uuid)
        ).scalar_one_or_none()
        if existing_rs is not None:
            stats["reading_skipped_existing"] += 1
            continue

        book_uri = rec.get("book_uri")
        uid = _unique_id_from_book_uri(book_uri)
        book = uid_to_book.get(uid) if uid else None
        if book is None and uid:
            book = session.execute(
                select(Book).where(Book.unique_id == uid)
            ).scalar_one_or_none()
            if book is not None:
                uid_to_book[uid] = book
        if book is None:
            # Reading session with no resolvable parent book: skip.
            stats["reading_orphaned"] += 1
            continue

        rs = ReadingSession(
            uuid=uuid,
            book_id=book.id,
            start_time=_parse_timestamp(rec.get("start_time")),
            end_time=_parse_timestamp(rec.get("end_time")),
            start_anchor=rec.get("start_anchor"),
            end_anchor=rec.get("end_anchor"),
            pages_read=rec.get("pages_read"),
        )
        session.add(rs)
        stats["reading_added"] += 1

    session.commit()
    return stats


def _merge_book_metadata(session, book, rec: Dict[str, Any]) -> None:
    """Merge author / subject / tag / identifier metadata into *book*.

    Only adds; never removes. Existing local enrichments survive.
    """
    from sqlalchemy import select

    from ..db.models import Author, Identifier, Subject, Tag

    # Authors.
    for name in rec.get("authors") or []:
        if not name:
            continue
        author = session.execute(
            select(Author).where(Author.name == name)
        ).scalar_one_or_none()
        if author is None:
            author = Author(name=name)
            session.add(author)
            session.flush()
        if author not in book.authors:
            book.authors.append(author)

    # Subjects.
    for name in rec.get("subjects") or []:
        if not name:
            continue
        subject = session.execute(
            select(Subject).where(Subject.name == name)
        ).scalar_one_or_none()
        if subject is None:
            subject = Subject(name=name)
            session.add(subject)
            session.flush()
        if subject not in book.subjects:
            book.subjects.append(subject)

    # Tags. Tags have full_path semantics; for the import we treat each
    # entry as a leaf name without re-deriving hierarchy (round-trip
    # between two book-memex archives preserves the same model in both).
    for tag_path in rec.get("tags") or []:
        if not tag_path:
            continue
        tag = session.execute(
            select(Tag).where(Tag.full_path == tag_path)
        ).scalar_one_or_none()
        if tag is None:
            # Split the path and create leaf-only Tag; hierarchy is not
            # reconstructed here because we don't know the parent_id
            # from the bundle. The consequence is flat tags for
            # round-tripped archives; a future pass can rebuild nesting.
            name = tag_path.rsplit("/", 1)[-1]
            tag = Tag(name=name)
            session.add(tag)
            session.flush()
        if tag not in book.tags:
            book.tags.append(tag)

    # Identifiers. Stored as {scheme: value}, not a Python object list.
    # We upsert by (book_id, scheme).
    for scheme, value in (rec.get("identifiers") or {}).items():
        if not scheme or not value:
            continue
        existing = session.execute(
            select(Identifier).where(
                Identifier.book_id == book.id,
                Identifier.scheme == scheme,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(Identifier(book_id=book.id, scheme=scheme, value=str(value)))
