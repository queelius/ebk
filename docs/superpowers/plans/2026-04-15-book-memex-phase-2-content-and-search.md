# book-memex Phase 2: Content Extraction and Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-file `TextChunk` table with per-segment `BookContent` (chapter / page / text), add FTS5 content index, build EPUB/PDF/TXT extractors, expose within-book and cross-library search over REST + MCP, and ship `ask_book(book_id, question)` using FTS5 + LLM retrieval (no embeddings).

**Architecture:** Extend (not duplicate) existing structures. `text_chunks` is renamed and refined in place via migration 11, with legacy rows kept via placeholder values and reindexed on demand. A new `book_content_fts` virtual table mirrors `book_content` via triggers, mirroring the pattern already used for `books_fts`. Extractors follow a `Protocol` interface and are dispatched by `Book.primary_file.format`. Search endpoints return both raw JSON anchors and pre-built URI fragments so REST, MCP, and a future reader UI can all use them without reshaping. `ask_book` uses the raw question as its FTS5 query (no pre-LLM keyword extraction in v1) and calls a configured LLM for answer generation.

**Tech Stack:** Python 3.12+, SQLAlchemy, FastAPI, FastMCP, Typer, SQLite 3.35+ (WAL + FTS5 + ALTER TABLE DROP COLUMN), ebooklib + BeautifulSoup (EPUB extraction), pypdf (PDF extraction), Anthropic SDK (LLM for `ask_book`; pluggable).

**Pre-flight:**
- Working directory: `/home/spinoza/github/memex/ebk/`.
- Dependencies: Phase 1 merged to master as of commit `ed1e6d8`. CURRENT_SCHEMA_VERSION = 10.
- Existing test baseline before Phase 2: 1021 tests passing, 5 skipped.
- Each task's commit leaves the suite green. Run `pytest -q --tb=no 2>&1 | tail -3` after every task.
- `book-memex` (preferred) and `ebk` (deprecated) CLI both resolve after Phase 1.
- Python package is `book_memex/`. Directory on disk is still `ebk/`.

---

## File structure

Files created or heavily modified in Phase 2:

```
book_memex/
├── core/
│   └── fts.py                              # NEW: safe_fts_query helper
├── db/
│   ├── migrations.py                       # MODIFIED: add migrations 11 and 12
│   ├── models.py                           # MODIFIED: TextChunk -> BookContent
│   └── session.py                          # MODIFIED: book_content_fts setup
├── services/
│   ├── content_extraction/                 # NEW: per-format extractors
│   │   ├── __init__.py                     # Protocol, Segment, dispatch
│   │   ├── epub.py                         # EpubExtractor v1
│   │   ├── pdf.py                          # PdfExtractor v1
│   │   └── txt.py                          # TxtExtractor v1
│   ├── content_indexer.py                  # NEW: extract + write BookContent
│   ├── import_service.py                   # MODIFIED: call indexer after cover
│   └── ask_book.py                         # NEW: FTS5 + LLM Q&A
├── mcp/
│   └── tools.py                            # MODIFIED: search + ask_book tools
├── server.py                               # MODIFIED: search endpoints
└── cli.py                                  # MODIFIED: extract + reindex-content
tests/
├── test_core_fts.py                        # NEW
├── test_migration_11_book_content.py       # NEW
├── test_migration_12_fts.py                # NEW
├── test_book_content_model.py              # NEW
├── test_content_extraction.py              # NEW (per-format)
├── test_content_indexer.py                 # NEW
├── test_content_indexer_on_import.py       # NEW (wiring)
├── test_cli_reindex.py                     # NEW
├── test_server_content_search.py           # NEW
├── test_mcp_content_tools.py               # NEW
├── test_ask_book.py                        # NEW
└── test_phase2_e2e.py                      # NEW
```

Legacy file: `TextChunk` is renamed in-place (no new class). `has_embedding` is dropped.

---

## Task 1: Migration 11 — rename `text_chunks` to `book_content`, add columns, drop `has_embedding`

**Files:**
- Modify: `book_memex/db/migrations.py`
- Create: `tests/test_migration_11_book_content.py`

SQLite operations used: `ALTER TABLE ... RENAME TO`, `ALTER TABLE ... RENAME COLUMN` (3.25+), `ALTER TABLE ... ADD COLUMN`, `ALTER TABLE ... DROP COLUMN` (3.35+). Index renames are recreated (drop + create).

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_11_book_content.py`:

```python
"""Test migration 11: text_chunks -> book_content with refined schema."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import (
    migrate_rename_text_chunks_to_book_content,
    get_schema_version,
    CURRENT_SCHEMA_VERSION,
)
from book_memex.library_db import Library


NEW_COLUMNS = {
    "id", "file_id", "content", "start_page", "end_page",
    "segment_type", "segment_index", "title", "anchor",
    "extractor_version", "extraction_status", "archived_at",
}


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_current_schema_version_at_least_11(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    assert get_schema_version(engine) >= 11
    assert CURRENT_SCHEMA_VERSION >= 11


def test_book_content_table_exists(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    tables = set(inspect(engine).get_table_names())
    assert "book_content" in tables
    assert "text_chunks" not in tables


def test_book_content_has_refined_columns(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
    assert cols >= NEW_COLUMNS, f"missing {NEW_COLUMNS - cols}"
    assert "has_embedding" not in cols
    assert "chunk_index" not in cols


def test_migration_is_idempotent(fresh_library):
    _, temp_dir = fresh_library
    applied = migrate_rename_text_chunks_to_book_content(temp_dir)
    assert applied is False


def test_legacy_rows_backfilled():
    """A pre-migration library with text_chunks rows must survive migration."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Stage 1: create a Library (runs all migrations through 10),
        # then manually recreate a legacy-shape row via raw SQL.
        lib = Library.open(temp_dir)
        with lib.session.begin():
            # The migration should have renamed to book_content; insert a
            # row that simulates a just-migrated legacy chunk.
            lib.session.execute(text("""
                INSERT INTO book_content
                  (file_id, content, start_page, end_page, segment_index,
                   segment_type, anchor, extractor_version, extraction_status)
                VALUES
                  (NULL, 'legacy body', 1, 5, 0,
                   'chunk-legacy', '{}', 'legacy', 'ok')
            """))
        lib.close()

        # Stage 2: reopen and confirm the row survives and migration logic
        # does not corrupt it on re-run.
        lib = Library.open(temp_dir)
        row = lib.session.execute(text(
            "SELECT segment_type, extractor_version, extraction_status "
            "FROM book_content WHERE content = 'legacy body'"
        )).first()
        lib.close()
        assert row is not None
        assert row[0] == "chunk-legacy"
        assert row[1] == "legacy"
        assert row[2] == "ok"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_11_book_content.py -q`
Expected: ImportError on `migrate_rename_text_chunks_to_book_content`, or AssertionError because `text_chunks` still exists.

- [ ] **Step 3: Implement migration 11**

Add to `book_memex/db/migrations.py` (near migration 10):

```python
def migrate_rename_text_chunks_to_book_content(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 11: rename text_chunks -> book_content with refined schema.

    - RENAME TABLE text_chunks -> book_content.
    - RENAME COLUMN chunk_index -> segment_index.
    - ADD COLUMN segment_type (default 'chunk-legacy' for existing rows).
    - ADD COLUMN title (nullable).
    - ADD COLUMN anchor (JSON, default '{}' for existing rows).
    - ADD COLUMN extractor_version (default 'legacy' for existing rows).
    - ADD COLUMN extraction_status (default 'ok').
    - ADD COLUMN archived_at (nullable).
    - DROP COLUMN has_embedding (per workspace 'no embeddings in archives').

    Existing rows are left in place with placeholder values marking them as
    legacy. The reindex-content CLI rewrites them from extracted files.
    """
    name = "rename_text_chunks_to_book_content"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        logger.debug(f"Migration {name} already applied")
        return False

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if dry_run:
        logger.info("DRY RUN: would rename text_chunks -> book_content and refine schema")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        # RENAME table if present and target not yet present.
        if "text_chunks" in tables and "book_content" not in tables:
            conn.execute(text("ALTER TABLE text_chunks RENAME TO book_content"))
        elif "book_content" not in tables:
            # Fresh install without text_chunks and without book_content.
            # Create a minimal book_content table; Base.metadata.create_all
            # may have already added it via the updated ORM; verify after.
            pass

        # Refresh inspector after rename.
        inspector = inspect(engine)
        if "book_content" not in set(inspector.get_table_names()):
            # ORM hasn't created it yet and no legacy table existed. Nothing to do.
            record_migration(engine, version=11, migration_name=name)
            return True

        cols = {c["name"] for c in inspector.get_columns("book_content")}

        # RENAME chunk_index -> segment_index.
        if "chunk_index" in cols and "segment_index" not in cols:
            conn.execute(text("ALTER TABLE book_content RENAME COLUMN chunk_index TO segment_index"))

        # ADD COLUMNs (idempotent per-column).
        add_columns = [
            ("segment_type", "VARCHAR(20) NOT NULL DEFAULT 'chunk-legacy'"),
            ("title", "VARCHAR(500)"),
            ("anchor", "JSON NOT NULL DEFAULT '{}'"),
            ("extractor_version", "VARCHAR(50) NOT NULL DEFAULT 'legacy'"),
            ("extraction_status", "VARCHAR(20) NOT NULL DEFAULT 'ok'"),
            ("archived_at", "TIMESTAMP NULL"),
        ]
        cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
        for col_name, col_ddl in add_columns:
            if col_name not in cols:
                conn.execute(text(f"ALTER TABLE book_content ADD COLUMN {col_name} {col_ddl}"))

        # DROP has_embedding if present.
        cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
        if "has_embedding" in cols:
            conn.execute(text("ALTER TABLE book_content DROP COLUMN has_embedding"))

        # Rebuild unique index on (file_id, segment_type, segment_index).
        # Old unique was (file_id, chunk_index); drop it if present.
        existing_indexes = {ix["name"] for ix in inspect(engine).get_indexes("book_content")}
        if "uix_chunk" in existing_indexes:
            conn.execute(text("DROP INDEX uix_chunk"))
        if "uix_book_content_file_seg" not in existing_indexes:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_book_content_file_seg "
                "ON book_content (file_id, segment_type, segment_index)"
            ))

    record_migration(engine, version=11, migration_name=name)
    return True
```

Update `MIGRATIONS`:

```python
MIGRATIONS = [
    # ... existing ...
    (10, "add_uri_columns", migrate_add_uri_columns),
    (11, "rename_text_chunks_to_book_content", migrate_rename_text_chunks_to_book_content),
]
```

Update the constant: `CURRENT_SCHEMA_VERSION = 11`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_11_book_content.py -q`
Expected: 5 passed.

- [ ] **Step 5: Run full suite to confirm no regression**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: 1026 passed (1021 + 5 new), 5 skipped.

- [ ] **Step 6: Commit**

```bash
git add book_memex/db/migrations.py tests/test_migration_11_book_content.py
git commit -m "$(cat <<'EOF'
feat(db): migration 11 - rename text_chunks to book_content

Renames table, renames chunk_index to segment_index, adds columns
segment_type / title / anchor / extractor_version / extraction_status
/ archived_at, drops has_embedding per workspace "no embeddings in
archives" convention. Legacy rows kept with placeholder values
(segment_type='chunk-legacy', extractor_version='legacy'); the
reindex-content CLI regenerates them with real extraction.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: ORM rename `TextChunk` → `BookContent` with refined columns

**Files:**
- Modify: `book_memex/db/models.py`
- Create: `tests/test_book_content_model.py`

Rename the class and update the `File.chunks` back-reference to `File.contents` (more accurate now). Preserve backward compatibility for any code importing `TextChunk` by leaving a class-level alias.

- [ ] **Step 1: Write the failing test**

Create `tests/test_book_content_model.py`:

```python
"""Test BookContent ORM model (renamed from TextChunk with refined schema)."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import BookContent, TextChunk


@pytest.fixture
def temp_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_book_content_is_sqlalchemy_class(temp_library):
    """BookContent should be usable as a normal ORM class."""
    bc = BookContent(
        file_id=None,
        content="hello world",
        segment_type="chapter",
        segment_index=0,
        title="Chapter 1",
        anchor={"cfi": "epubcfi(/6/2[chap01]!/4)"},
        extractor_version="epub-v1",
        extraction_status="ok",
    )
    temp_library.session.add(bc)
    temp_library.session.commit()

    fetched = temp_library.session.get(BookContent, bc.id)
    assert fetched.content == "hello world"
    assert fetched.segment_type == "chapter"
    assert fetched.segment_index == 0
    assert fetched.title == "Chapter 1"
    assert fetched.anchor == {"cfi": "epubcfi(/6/2[chap01]!/4)"}
    assert fetched.extractor_version == "epub-v1"
    assert fetched.extraction_status == "ok"
    assert fetched.archived_at is None


def test_text_chunk_alias_points_to_book_content():
    """Legacy imports of TextChunk must still resolve to the same class."""
    assert TextChunk is BookContent


def test_no_has_embedding_attribute(temp_library):
    """The has_embedding column was dropped."""
    assert not hasattr(BookContent, "has_embedding")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_book_content_model.py -q`
Expected: ImportError on `BookContent`, or AttributeError.

- [ ] **Step 3: Update ORM model**

Open `book_memex/db/models.py`. Find the existing `class TextChunk(Base)` definition and replace it:

```python
class BookContent(Base):
    """Extracted content segments (chapter / page / whole-file) for search and RAG.

    Renamed from TextChunk in migration 11. Each row is one addressable
    segment of a book file, produced by a format-specific extractor.
    Keyed by (file_id, segment_type, segment_index). Not URI-addressable
    directly; positions within a book are cited as Book URI fragments.
    """
    __tablename__ = 'book_content'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id', ondelete='CASCADE'), nullable=False)

    # Legacy column preserved.
    content = Column(Text, nullable=False)
    start_page = Column(Integer)
    end_page = Column(Integer)

    # Refined segmentation (migration 11).
    segment_type = Column(String(20), nullable=False)   # 'chapter' | 'page' | 'text' | 'chunk-legacy'
    segment_index = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    anchor = Column(JSON, nullable=False, default=dict)

    # Extractor provenance.
    extractor_version = Column(String(50), nullable=False, default='legacy')
    extraction_status = Column(String(20), nullable=False, default='ok')

    archived_at = Column(DateTime, nullable=True)

    file = relationship('File', back_populates='contents')

    __table_args__ = (
        UniqueConstraint('file_id', 'segment_type', 'segment_index',
                         name='uix_book_content_file_seg'),
        Index('idx_book_content_file', 'file_id'),
        Index('idx_book_content_archived', 'archived_at'),
    )

    def __repr__(self):
        return (
            f"<BookContent(id={self.id}, file_id={self.file_id}, "
            f"type={self.segment_type}, index={self.segment_index})>"
        )


# Backward-compat alias for any pre-Phase-2 code still importing TextChunk.
TextChunk = BookContent
```

Update the `File` class's relationship. Find the existing line `chunks = relationship('TextChunk', ...)` and change to:

```python
    contents = relationship('BookContent', back_populates='file', cascade='all, delete-orphan')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_book_content_model.py -q`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: 1029 passed (1026 + 3 new), 5 skipped.

If any existing test fails due to `File.chunks` being renamed to `File.contents`, update those tests — or add a `chunks` alias property on File temporarily.

- [ ] **Step 6: Commit**

```bash
git add book_memex/db/models.py tests/test_book_content_model.py
git commit -m "$(cat <<'EOF'
feat(db): rename TextChunk ORM -> BookContent with refined schema

- segment_type / segment_index / title / anchor / extractor_version /
  extraction_status / archived_at exposed via ORM.
- has_embedding dropped from ORM (column dropped in migration 11).
- File.chunks -> File.contents (more accurate).
- TextChunk = BookContent alias preserved for any legacy importers.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Migration 12 — `book_content_fts` virtual table + triggers

**Files:**
- Modify: `book_memex/db/migrations.py`
- Modify: `book_memex/db/session.py` (ensure FTS table is created alongside existing `books_fts`)
- Create: `tests/test_migration_12_fts.py`

Add an FTS5 virtual table mirroring `book_content` via `content=` (external content). Triggers sync inserts/updates/deletes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_12_fts.py`:

```python
"""Test migration 12: book_content_fts virtual table + triggers."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import CURRENT_SCHEMA_VERSION
from book_memex.db.models import BookContent
from book_memex.library_db import Library


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_schema_version_at_least_12(fresh_library):
    assert CURRENT_SCHEMA_VERSION >= 12


def test_book_content_fts_exists(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    tables = set(inspect(engine).get_table_names())
    assert "book_content_fts" in tables


def test_insert_syncs_to_fts(fresh_library):
    lib, temp_dir = fresh_library
    bc = BookContent(
        file_id=None, content="the quick brown fox",
        segment_type="chapter", segment_index=0, title="Intro",
        anchor={}, extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()

    # Query FTS directly.
    rows = lib.session.execute(text(
        "SELECT rowid FROM book_content_fts WHERE book_content_fts MATCH 'quick fox'"
    )).fetchall()
    assert any(r[0] == bc.id for r in rows)


def test_update_syncs_to_fts(fresh_library):
    lib, temp_dir = fresh_library
    bc = BookContent(
        file_id=None, content="apple",
        segment_type="chapter", segment_index=0, anchor={},
        extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()

    bc.content = "banana"
    lib.session.commit()

    apple_hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'apple'"
    )).scalar()
    banana_hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'banana'"
    )).scalar()
    assert apple_hits == 0
    assert banana_hits == 1


def test_delete_syncs_to_fts(fresh_library):
    lib, temp_dir = fresh_library
    bc = BookContent(
        file_id=None, content="ephemeral",
        segment_type="chapter", segment_index=0, anchor={},
        extractor_version="epub-v1", extraction_status="ok",
    )
    lib.session.add(bc)
    lib.session.commit()
    lib.session.delete(bc)
    lib.session.commit()

    hits = lib.session.execute(text(
        "SELECT count(*) FROM book_content_fts WHERE book_content_fts MATCH 'ephemeral'"
    )).scalar()
    assert hits == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_12_fts.py -q`
Expected: failures because `book_content_fts` does not exist.

- [ ] **Step 3: Implement migration 12**

Add to `book_memex/db/migrations.py`:

```python
def migrate_add_book_content_fts(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 12: add book_content_fts virtual table plus sync triggers.

    FTS5 mirrors book_content's `content` + `title` columns. Uses external
    content addressing (content='book_content', content_rowid='id') so the
    FTS index and the row table stay in sync via AFTER INSERT/UPDATE/DELETE
    triggers. Matches the existing books_fts pattern.
    """
    name = "add_book_content_fts"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        return False

    if dry_run:
        logger.info("DRY RUN: would create book_content_fts virtual table + triggers")
        return True

    inspector = inspect(engine)
    if "book_content" not in set(inspector.get_table_names()):
        # Nothing to index yet. Record migration anyway so it isn't retried.
        record_migration(engine, version=12, migration_name=name)
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS book_content_fts USING fts5(
                text,
                title,
                book_id UNINDEXED,
                content_id UNINDEXED,
                content='book_content',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """))

        # Populate from any existing rows.
        conn.execute(text("""
            INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
            SELECT bc.id, bc.content, COALESCE(bc.title, ''),
                   COALESCE(f.book_id, 0), bc.id
            FROM book_content bc
            LEFT JOIN files f ON f.id = bc.file_id
        """))

        # AFTER INSERT.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_ai AFTER INSERT ON book_content BEGIN
                INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
                VALUES (new.id, new.content, COALESCE(new.title, ''),
                        (SELECT book_id FROM files WHERE id = new.file_id), new.id);
            END
        """))

        # AFTER UPDATE of text/title.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_au AFTER UPDATE ON book_content BEGIN
                INSERT INTO book_content_fts (book_content_fts, rowid, text, title, book_id, content_id)
                VALUES ('delete', old.id, old.content, COALESCE(old.title, ''),
                        (SELECT book_id FROM files WHERE id = old.file_id), old.id);
                INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
                VALUES (new.id, new.content, COALESCE(new.title, ''),
                        (SELECT book_id FROM files WHERE id = new.file_id), new.id);
            END
        """))

        # AFTER DELETE.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_ad AFTER DELETE ON book_content BEGIN
                INSERT INTO book_content_fts (book_content_fts, rowid, text, title, book_id, content_id)
                VALUES ('delete', old.id, old.content, COALESCE(old.title, ''),
                        (SELECT book_id FROM files WHERE id = old.file_id), old.id);
            END
        """))

    record_migration(engine, version=12, migration_name=name)
    return True
```

Update MIGRATIONS list:

```python
MIGRATIONS = [
    # ... existing ...
    (11, "rename_text_chunks_to_book_content", migrate_rename_text_chunks_to_book_content),
    (12, "add_book_content_fts", migrate_add_book_content_fts),
]
```

Update: `CURRENT_SCHEMA_VERSION = 12`.

- [ ] **Step 4: Ensure `session.py` does NOT pre-create `book_content_fts`**

Open `book_memex/db/session.py`. The `init_db` function calls `Base.metadata.create_all(_engine)` plus hand-rolled FTS setup for `books_fts`. Do NOT add `book_content_fts` creation here — it's handled entirely by migration 12 so that the FTS triggers and the backfill stay in one place.

If the existing init has a generic "create FTS tables" helper that uses convention, keep that helper to `books_fts` only.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_migration_12_fts.py -q`
Expected: 5 passed.

- [ ] **Step 6: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: 1034 passed, 5 skipped.

- [ ] **Step 7: Commit**

```bash
git add book_memex/db/migrations.py book_memex/db/session.py tests/test_migration_12_fts.py
git commit -m "$(cat <<'EOF'
feat(db): migration 12 - book_content_fts virtual table + triggers

FTS5 over (text, title) mirroring book_content via external-content
addressing. AFTER INSERT/UPDATE/DELETE triggers keep the index in
sync, matching the existing books_fts pattern. Backfills from any
rows present at migration time.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `safe_fts_query` helper

**Files:**
- Create: `book_memex/core/fts.py`
- Create: `tests/test_core_fts.py`

FTS5 queries use special syntax (AND, OR, NEAR, `-`, `*`, quoted phrases). User input needs escaping. Default behavior: wrap each token as a phrase. Opt-in: pass raw FTS5 syntax through.

- [ ] **Step 1: Write the failing test**

Create `tests/test_core_fts.py`:

```python
"""Unit tests for book_memex.core.fts."""
import pytest

from book_memex.core.fts import safe_fts_query


class TestBasicEscaping:
    def test_single_word_wrapped_as_phrase(self):
        assert safe_fts_query("bayesian") == '"bayesian"'

    def test_multiple_words_wrapped_individually(self):
        # Each token becomes its own phrase; FTS5 AND-joins implicit phrases.
        assert safe_fts_query("bayesian inference") == '"bayesian" "inference"'

    def test_special_chars_inside_phrase(self):
        # Double-quote escaped by doubling (FTS5 convention).
        result = safe_fts_query('foo "bar" baz')
        # tokens: foo, "bar", baz -> "foo" """"bar"""" "baz" (FTS5 embeds " as "")
        # Tokenizer splits on quotes, so we get three phrases: foo, bar, baz
        assert '"foo"' in result
        assert '"bar"' in result
        assert '"baz"' in result

    def test_operator_keywords_escaped(self):
        # AND is an FTS5 operator; when wrapped as phrase, it is treated literally.
        result = safe_fts_query("foo AND bar")
        assert result == '"foo" "AND" "bar"'

    def test_wildcard_literal(self):
        assert safe_fts_query("foo*") == '"foo*"'

    def test_hyphen_literal(self):
        assert safe_fts_query("foo-bar") == '"foo-bar"'

    def test_empty_string_returns_empty(self):
        assert safe_fts_query("") == ""

    def test_whitespace_only_returns_empty(self):
        assert safe_fts_query("   \t\n  ") == ""


class TestAdvancedMode:
    def test_advanced_passes_raw(self):
        q = 'quantum NEAR(gravity, 5)'
        assert safe_fts_query(q, advanced=True) == q

    def test_advanced_preserves_operators(self):
        assert safe_fts_query("foo AND bar", advanced=True) == "foo AND bar"


class TestUnicode:
    def test_unicode_passed_through(self):
        assert safe_fts_query("über café") == '"über" "café"'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core_fts.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement the helper**

Create `book_memex/core/fts.py`:

```python
"""FTS5 query-safety helper.

User input is passed through `safe_fts_query()` before being handed to
FTS5's MATCH. By default each token is wrapped as a phrase, which makes
FTS5 operators (AND, OR, NEAR), prefix wildcards (*), and sign operators
(- !) inert. Callers who want to opt into raw FTS5 syntax pass
advanced=True.
"""

from __future__ import annotations

import re

# Whitespace-based tokenization. Also split on double quotes so that
# a user typing `foo "bar" baz` gets three tokens: foo, bar, baz.
_TOKENIZER = re.compile(r'[^\s"]+')


def safe_fts_query(user_input: str, *, advanced: bool = False) -> str:
    """Convert a user-provided search string into a safe FTS5 MATCH query.

    In default mode, each whitespace-separated token is wrapped in double
    quotes (FTS5 phrase syntax), which treats operators and special chars
    as literal text. Empty input returns an empty string.

    In advanced mode, the input is returned as-is. Callers opt in via
    advanced=True when they want to expose raw FTS5 syntax (wildcards,
    NEAR, AND/OR) to power users.
    """
    if not isinstance(user_input, str):
        raise TypeError(f"expected str, got {type(user_input).__name__}")

    if advanced:
        return user_input

    if not user_input.strip():
        return ""

    tokens = _TOKENIZER.findall(user_input)
    if not tokens:
        return ""

    # FTS5 escapes embedded double quotes by doubling them.
    quoted = [f'"{t.replace(chr(34), chr(34) * 2)}"' for t in tokens]
    return " ".join(quoted)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core_fts.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add book_memex/core/fts.py tests/test_core_fts.py
git commit -m "$(cat <<'EOF'
feat(core): add safe_fts_query helper

Wraps user tokens as FTS5 phrases by default, making AND/OR/NEAR,
wildcards, and sign operators inert. Advanced mode passes input
through unchanged for power users.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Extractor Protocol + `Segment` dataclass

**Files:**
- Create: `book_memex/services/content_extraction/__init__.py`
- Create: `tests/test_content_extraction.py` (basic interface tests; per-format tests in later tasks)

Defines the common contract. Individual extractors land in tasks 6-8.

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_extraction.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_extraction.py -q`
Expected: ImportError.

- [ ] **Step 3: Create the package and protocol**

Create `book_memex/services/content_extraction/__init__.py`:

```python
"""Content extraction for book files.

Each format-specific extractor implements the Extractor Protocol, yielding
Segment records. The dispatch helper get_extractor(format) returns the
right instance. Versioning lets book-memex reindex specific books when an
extractor improves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, Optional, Protocol, runtime_checkable


@dataclass
class Segment:
    """One extracted piece of a book file.

    segment_type:
        "chapter" for EPUBs (one per spine item),
        "page" for PDFs (one per page),
        "text" for whole-file TXT/MD.
    segment_index:
        Stable index within the book. Combined with segment_type, forms
        a durable intra-book identifier.
    anchor:
        Content-intrinsic position pointer, JSON-safe.
        EPUB: {"cfi": "epubcfi(...)"}, PDF: {"page": <1-based>},
        TXT: {"offset": 0, "length": <n>}.
    extraction_status:
        "ok" for normal segments; "no_text_layer" for scanned PDFs;
        "partial" for segments where extraction succeeded but may be
        incomplete (e.g., DRM-protected chunks).
    """
    segment_type: str
    segment_index: int
    title: Optional[str]
    anchor: Dict
    text: str
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    extraction_status: str = "ok"


@runtime_checkable
class Extractor(Protocol):
    """Format-specific content extractor."""

    version: str  # e.g., "epub-v1", "pdf-v1", "txt-v1"

    def supports(self, book_format: str) -> bool: ...

    def extract(self, file_path: Path) -> Iterator[Segment]: ...


_REGISTRY: Dict[str, Extractor] = {}
SUPPORTED_FORMATS = ("epub", "pdf", "txt")


def register(fmt: str, extractor: Extractor) -> None:
    """Register an extractor for a file format. Later registrations override."""
    _REGISTRY[fmt.lower()] = extractor


def get_extractor(book_format: str) -> Extractor:
    """Return the registered extractor for a format. Raises ValueError if unknown."""
    ex = _REGISTRY.get(book_format.lower())
    if ex is None:
        raise ValueError(f"no extractor registered for format {book_format!r}")
    return ex


# Lazy registration: extractors self-register on import.
def _install_default_extractors() -> None:
    from book_memex.services.content_extraction.epub import EpubExtractor
    from book_memex.services.content_extraction.pdf import PdfExtractor
    from book_memex.services.content_extraction.txt import TxtExtractor
    register("epub", EpubExtractor())
    register("pdf", PdfExtractor())
    register("txt", TxtExtractor())


_install_default_extractors()
```

- [ ] **Step 4: Run test to verify it still fails (because the per-format extractors don't exist yet)**

Run: `pytest tests/test_content_extraction.py -q`
Expected: ImportError from `epub.py` / `pdf.py` / `txt.py` during `_install_default_extractors`.

- [ ] **Step 5: Create stub extractor files**

Create each of the three per-format stubs so the package imports cleanly. Full implementations arrive in Tasks 6-8.

`book_memex/services/content_extraction/epub.py`:

```python
"""EPUB content extractor (Task 6 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class EpubExtractor:
    version = "epub-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "epub"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("EpubExtractor.extract arrives in Task 6")
```

`book_memex/services/content_extraction/pdf.py`:

```python
"""PDF content extractor (Task 7 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class PdfExtractor:
    version = "pdf-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "pdf"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("PdfExtractor.extract arrives in Task 7")
```

`book_memex/services/content_extraction/txt.py`:

```python
"""TXT content extractor (Task 8 fills in the body)."""
from pathlib import Path
from typing import Iterator

from . import Segment


class TxtExtractor:
    version = "txt-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() in ("txt", "md")

    def extract(self, file_path: Path) -> Iterator[Segment]:
        raise NotImplementedError("TxtExtractor.extract arrives in Task 8")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_content_extraction.py -q`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add book_memex/services/content_extraction/ tests/test_content_extraction.py
git commit -m "$(cat <<'EOF'
feat(content-extraction): add Extractor protocol + Segment dataclass

Defines the common contract for per-format extractors (epub, pdf, txt),
plus a registry so get_extractor(format) dispatches to the right one.
Per-format extractors are stubs; their bodies arrive in the next three
tasks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `EpubExtractor` implementation

**Files:**
- Modify: `book_memex/services/content_extraction/epub.py`
- Create: `tests/fixtures/sample.epub` (tiny fixture)
- Add tests to: `tests/test_content_extraction.py`

Uses `ebooklib` (already a project dependency) to parse the EPUB. Walks the spine; one segment per spine item. Title from HTML `<h1>` or `<title>`. Anchor is a chapter-root CFI derived from spine position.

- [ ] **Step 1: Create a tiny test fixture EPUB**

Use `ebooklib` to construct an EPUB programmatically in a conftest fixture (rather than shipping a binary). Append to `tests/conftest.py` (or create one if it does not already have a `sample_epub` fixture):

```python
import os
import tempfile
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
            content=f"<?xml version='1.0' encoding='utf-8'?>"
                    f"<html xmlns='http://www.w3.org/1999/xhtml'><body>{body}</body></html>",
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
```

- [ ] **Step 2: Write the failing test**

Add to `tests/test_content_extraction.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_content_extraction.py -q -k epub`
Expected: NotImplementedError.

- [ ] **Step 4: Implement the extractor**

Replace `book_memex/services/content_extraction/epub.py`:

```python
"""EPUB content extractor.

Walks the EPUB spine, emitting one Segment per document item (skipping
the nav). Title is extracted from the first <h1> when present, falling
back to the spine item's TOC title. Anchor is a chapter-root CFI derived
from the spine position (even-index pattern: item N occupies CFI /6/<2N>).
"""

from pathlib import Path
from typing import Iterator, Optional

from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT

from . import Segment


class EpubExtractor:
    version = "epub-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "epub"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        book = epub.read_epub(str(file_path))

        # Walk the spine in order. `book.spine` is a list of (item_id, linear)
        # tuples. The nav item is typically first and is not content; skip it.
        document_items = []
        for spine_entry in book.spine:
            item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
            item = book.get_item_with_id(item_id)
            if item is None:
                continue
            if item.get_type() != ITEM_DOCUMENT:
                continue
            # Heuristic: skip common nav filename patterns.
            href = (item.get_name() or "").lower()
            if "nav" in href or href.endswith(("toc.xhtml", "toc.html")):
                continue
            document_items.append(item)

        for index, item in enumerate(document_items):
            raw = item.get_body_content() or item.get_content()
            soup = BeautifulSoup(raw, "html.parser")

            # Title: first <h1>, else <title>, else the item's own attribute.
            title = None
            h1 = soup.find("h1")
            if h1 is not None and h1.get_text(strip=True):
                title = h1.get_text(strip=True)
            else:
                title_tag = soup.find("title")
                if title_tag is not None and title_tag.get_text(strip=True):
                    title = title_tag.get_text(strip=True)
            if not title:
                title = getattr(item, "title", None) or None

            text = _clean_text(soup.get_text(separator=" ", strip=True))

            # Simplified CFI: /6/<2*(index+1)>[<item_id>]!/4 points at the
            # body of the chapter. Real CFI generation requires inspecting
            # the OPF; this form resolves in EPUB.js's Rendition.display().
            cfi = f"epubcfi(/6/{(index + 1) * 2}[{item.get_id()}]!/4)"

            yield Segment(
                segment_type="chapter",
                segment_index=index,
                title=title,
                anchor={"cfi": cfi},
                text=text,
                extraction_status="ok",
            )


def _clean_text(text: str) -> str:
    """Collapse runs of whitespace; trim ends."""
    return " ".join(text.split())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_content_extraction.py -q -k epub`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add book_memex/services/content_extraction/epub.py tests/conftest.py tests/test_content_extraction.py
git commit -m "$(cat <<'EOF'
feat(content-extraction): EpubExtractor v1

Walks the EPUB spine via ebooklib, emitting one Segment per document
item (skipping nav). Title comes from <h1>/<title>/TOC fallback.
Anchor is a chapter-root CFI derived from spine position (resolvable
by EPUB.js's rendition.display).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `PdfExtractor` implementation

**Files:**
- Modify: `book_memex/services/content_extraction/pdf.py`
- Add tests to: `tests/test_content_extraction.py`
- Optional fixture: `tests/fixtures/sample.pdf` (generated on the fly in conftest)

Per-page extraction via `pypdf`. Anchor is `{"page": N}` (1-based to match user expectations). `extraction_status` is `"no_text_layer"` when a page's extracted text is empty or near-empty.

- [ ] **Step 1: Add PDF fixture to conftest**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def sample_pdf(tmp_path):
    """A 3-page PDF constructed with pypdf for extractor tests."""
    from pypdf import PdfWriter
    from pypdf.generic import ContentStream, create_string_object
    # Simpler path: use reportlab if available, else a minimal PdfWriter.
    # reportlab is not a core dep; fall back to a 3-page blank PDF and
    # write text-like content via pypdf's own API.
    try:
        from reportlab.pdfgen import canvas
        out = tmp_path / "sample.pdf"
        c = canvas.Canvas(str(out))
        for i, body in enumerate([
            "Page one quick brown fox.",
            "Page two Bayesian inference.",
            "Page three the conclusion.",
        ]):
            c.drawString(72, 720, body)
            c.showPage()
        c.save()
        return out
    except ImportError:
        pytest.skip("reportlab not installed; PDF fixture unavailable")
```

If `reportlab` is not already a dev dep, add it to pyproject.toml `[project.optional-dependencies] dev` alongside pytest. Otherwise use a different PDF generation route.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_content_extraction.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_content_extraction.py -q -k pdf`
Expected: NotImplementedError.

- [ ] **Step 4: Implement the extractor**

Replace `book_memex/services/content_extraction/pdf.py`:

```python
"""PDF content extractor.

One Segment per page. Anchor is {"page": <1-based>}. Pages with empty or
near-empty text (< 5 non-whitespace chars) are flagged
extraction_status="no_text_layer" so downstream consumers can surface
the fact instead of silently indexing nothing.
"""

from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

from . import Segment


_MIN_PAGE_TEXT_CHARS = 5


class PdfExtractor:
    version = "pdf-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() == "pdf"

    def extract(self, file_path: Path) -> Iterator[Segment]:
        reader = PdfReader(str(file_path))
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            stripped = text.strip()
            status = "ok" if len(stripped) >= _MIN_PAGE_TEXT_CHARS else "no_text_layer"
            yield Segment(
                segment_type="page",
                segment_index=i,
                title=None,
                anchor={"page": i + 1},  # 1-based
                text=stripped if status == "ok" else "",
                start_page=i + 1,
                end_page=i + 1,
                extraction_status=status,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_content_extraction.py -q -k pdf`
Expected: 4 passed (3 for text-bearing PDF, 1 for blank PDF).

If `reportlab` is not installed, the text-bearing tests skip. That is acceptable for v1; the blank-PDF test still validates the no-text-layer path.

- [ ] **Step 6: Commit**

```bash
git add book_memex/services/content_extraction/pdf.py tests/conftest.py tests/test_content_extraction.py pyproject.toml
git commit -m "$(cat <<'EOF'
feat(content-extraction): PdfExtractor v1

One Segment per page via pypdf. Anchor is {"page": <1-based>}. Pages
with empty or near-empty text are flagged extraction_status =
"no_text_layer" (emitted as empty-text segments so the shape stays
consistent but callers can surface the condition).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `TxtExtractor` implementation

**Files:**
- Modify: `book_memex/services/content_extraction/txt.py`
- Add tests to: `tests/test_content_extraction.py`

One segment per file. Anchor is `{"offset": 0, "length": <n>}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_content_extraction.py`:

```python
def test_txt_extractor_single_segment(tmp_path):
    from book_memex.services.content_extraction import get_extractor

    p = tmp_path / "sample.txt"
    body = "Plain text content, one segment.\n"
    p.write_text(body, encoding="utf-8")

    ex = get_extractor("txt")
    segments = list(ex.extract(p))
    assert len(segments) == 1
    s = segments[0]
    assert s.segment_type == "text"
    assert s.segment_index == 0
    assert s.text.strip() == body.strip()
    assert s.anchor == {"offset": 0, "length": len(body)}
    assert s.extraction_status == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_extraction.py -q -k txt`
Expected: NotImplementedError.

- [ ] **Step 3: Implement**

Replace `book_memex/services/content_extraction/txt.py`:

```python
"""TXT/MD content extractor.

Emits exactly one Segment containing the entire file. Encoding is
utf-8 with "replace" errors so malformed bytes do not halt extraction.
Anchor is {"offset": 0, "length": <byte count>}.
"""

from pathlib import Path
from typing import Iterator

from . import Segment


class TxtExtractor:
    version = "txt-v1"

    def supports(self, book_format: str) -> bool:
        return book_format.lower() in ("txt", "md")

    def extract(self, file_path: Path) -> Iterator[Segment]:
        data = file_path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        yield Segment(
            segment_type="text",
            segment_index=0,
            title=None,
            anchor={"offset": 0, "length": len(data)},
            text=text,
            extraction_status="ok",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_extraction.py -q -k txt`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add book_memex/services/content_extraction/txt.py tests/test_content_extraction.py
git commit -m "feat(content-extraction): TxtExtractor v1 (whole-file segment)"
```

---

## Task 9: Content indexer — orchestrate extraction + write BookContent

**Files:**
- Create: `book_memex/services/content_indexer.py`
- Create: `tests/test_content_indexer.py`

The indexer receives a File row, selects the extractor by format, iterates the extractor, writes BookContent rows atomically, and returns a summary. Handles re-indexing (deletes existing rows for that file before inserting).

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_indexer.py`:

```python
"""Tests for ContentIndexer: run extractor and write BookContent rows."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import BookContent, File
from book_memex.services.content_indexer import ContentIndexer, IndexResult


@pytest.fixture
def lib_with_epub(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    # Copy EPUB into the library and import via add_book.
    dest = lib.library_path / "sample.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(
        dest,
        metadata={"title": "Phase 2 Sample", "creators": ["Test Author"]},
        extract_text=False,  # we drive extraction manually below
    )
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_index_file_writes_segments(lib_with_epub):
    lib, book = lib_with_epub
    file_row = book.primary_file
    assert file_row is not None

    indexer = ContentIndexer(lib.session, lib.library_path)
    result = indexer.index_file(file_row)

    assert isinstance(result, IndexResult)
    assert result.segments_written == 3
    assert result.status == "ok"
    assert result.extractor_version == "epub-v1"

    rows = (
        lib.session.query(BookContent)
        .filter(BookContent.file_id == file_row.id)
        .order_by(BookContent.segment_index)
        .all()
    )
    assert len(rows) == 3
    assert all(r.segment_type == "chapter" for r in rows)


def test_reindex_replaces_prior_rows(lib_with_epub):
    lib, book = lib_with_epub
    file_row = book.primary_file
    indexer = ContentIndexer(lib.session, lib.library_path)

    indexer.index_file(file_row)
    first_ids = {
        r.id for r in lib.session.query(BookContent)
                                  .filter(BookContent.file_id == file_row.id).all()
    }
    assert len(first_ids) == 3

    # Reindex: old rows should be replaced, so ids change.
    indexer.index_file(file_row)
    second_ids = {
        r.id for r in lib.session.query(BookContent)
                                  .filter(BookContent.file_id == file_row.id).all()
    }
    assert len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids), "reindex should produce new row ids"


def test_index_unsupported_format_records_failure(lib_with_epub):
    lib, book = lib_with_epub
    # Fabricate a File with an unsupported format for negative-path testing.
    bogus_file = File(
        book_id=book.id,
        path="bogus.xyz",
        format="xyz",
        file_hash="0" * 64,
        size_bytes=0,
    )
    lib.session.add(bogus_file)
    lib.session.commit()

    indexer = ContentIndexer(lib.session, lib.library_path)
    result = indexer.index_file(bogus_file)

    assert result.status == "unsupported_format"
    assert result.segments_written == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_indexer.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement the indexer**

Create `book_memex/services/content_indexer.py`:

```python
"""Content indexer: run an extractor over a File and write BookContent rows.

Atomic per-file reindex: old rows for the file are deleted before new rows
are inserted. FTS triggers keep book_content_fts in sync automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from book_memex.db.models import BookContent, File
from book_memex.services.content_extraction import (
    Segment, get_extractor,
)


logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    file_id: Optional[int]
    status: str  # "ok" | "unsupported_format" | "extractor_error" | "no_text_layer"
    segments_written: int
    extractor_version: Optional[str]
    detail: Optional[str] = None


class ContentIndexer:
    """Extract + persist book segments for a File row."""

    def __init__(self, session: Session, library_path: Optional[Path] = None):
        self.session = session
        self.library_path = library_path

    def index_file(self, file_row: File) -> IndexResult:
        """Extract content from `file_row` and write BookContent rows.

        Deletes any existing BookContent rows for the file first.
        Returns an IndexResult summarizing the outcome.
        """
        try:
            extractor = get_extractor(file_row.format)
        except ValueError as exc:
            logger.info(
                "skip unsupported format %r for file_id=%s: %s",
                file_row.format, file_row.id, exc,
            )
            return IndexResult(
                file_id=file_row.id,
                status="unsupported_format",
                segments_written=0,
                extractor_version=None,
                detail=str(exc),
            )

        file_path = self._resolve_path(file_row)

        # Clear existing rows for this file (idempotent reindex).
        self.session.query(BookContent).filter(BookContent.file_id == file_row.id).delete(
            synchronize_session=False
        )
        self.session.flush()

        segments_written = 0
        statuses = set()
        try:
            for seg in extractor.extract(file_path):
                row = BookContent(
                    file_id=file_row.id,
                    content=seg.text,
                    segment_type=seg.segment_type,
                    segment_index=seg.segment_index,
                    title=seg.title,
                    anchor=seg.anchor,
                    start_page=seg.start_page,
                    end_page=seg.end_page,
                    extractor_version=extractor.version,
                    extraction_status=seg.extraction_status,
                )
                self.session.add(row)
                segments_written += 1
                statuses.add(seg.extraction_status)
        except Exception as exc:
            logger.exception("extractor error for file_id=%s", file_row.id)
            self.session.rollback()
            return IndexResult(
                file_id=file_row.id,
                status="extractor_error",
                segments_written=0,
                extractor_version=extractor.version,
                detail=str(exc),
            )

        self.session.commit()

        # Aggregate status: if any segment was ok, treat result as ok; if all
        # segments were no_text_layer, escalate that to the result.
        if "ok" in statuses:
            status = "ok"
        elif statuses == {"no_text_layer"}:
            status = "no_text_layer"
        else:
            status = "ok" if segments_written else "extractor_error"

        return IndexResult(
            file_id=file_row.id,
            status=status,
            segments_written=segments_written,
            extractor_version=extractor.version,
        )

    def _resolve_path(self, file_row: File) -> Path:
        """Absolute path to the file on disk."""
        rel = Path(file_row.path)
        if rel.is_absolute():
            return rel
        if self.library_path is None:
            return rel
        return self.library_path / rel
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_indexer.py -q`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: prior total + ~16 new tests (extractor interface + per-format + indexer), no failures.

- [ ] **Step 6: Commit**

```bash
git add book_memex/services/content_indexer.py tests/test_content_indexer.py
git commit -m "$(cat <<'EOF'
feat(services): ContentIndexer orchestrates extract + write BookContent

index_file() selects an extractor by File.format, clears prior rows
for the file, iterates segments, inserts BookContent rows, and
commits. Returns IndexResult summarizing segments_written, status,
and extractor_version. Reindexing is idempotent (replaces rows).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire `ContentIndexer` into `ImportService`

**Files:**
- Modify: `book_memex/services/import_service.py`
- Create: `tests/test_content_indexer_on_import.py`

After metadata and cover extraction, run the indexer on the newly imported file. Do not fail the import if the indexer errors; record the status.

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_indexer_on_import.py`:

```python
"""Verify that importing a book triggers content indexing."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import BookContent


@pytest.fixture
def tmp_lib():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_importing_epub_writes_book_content(tmp_lib, sample_epub):
    dest = tmp_lib.library_path / "imported.epub"
    shutil.copy(sample_epub, dest)
    book = tmp_lib.add_book(
        dest,
        metadata={"title": "Imported", "creators": ["A"]},
        extract_text=True,  # new extract_text path now runs content indexer too
    )

    rows = (
        tmp_lib.session.query(BookContent)
        .filter(BookContent.file_id == book.primary_file.id)
        .all()
    )
    assert len(rows) == 3
    assert all(r.extractor_version == "epub-v1" for r in rows)


def test_importing_unsupported_format_still_succeeds(tmp_lib, tmp_path):
    """A format with no extractor imports normally; just no BookContent rows."""
    unknown = tmp_lib.library_path / "mystery.xyz"
    unknown.write_bytes(b"not a known format")
    book = tmp_lib.add_book(
        unknown,
        metadata={"title": "Mystery", "creators": ["B"]},
        extract_text=True,
    )
    # Import succeeded; no content rows.
    rows = (
        tmp_lib.session.query(BookContent)
        .filter(BookContent.file_id == book.primary_file.id)
        .all()
    )
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_indexer_on_import.py -q`
Expected: `len(rows) == 3` fails because the indexer isn't wired.

- [ ] **Step 3: Modify `import_service.py`**

Open `book_memex/services/import_service.py`. Locate the `_create_book` or equivalent method that finalizes a new Book + File. After the existing `text_extraction` call (if one exists), add:

```python
# Run the segment-level content indexer for the newly imported file.
# Failures are logged but do not abort the import.
try:
    from book_memex.services.content_indexer import ContentIndexer
    indexer = ContentIndexer(self.session, library_path=self.library_path)
    primary = book.primary_file
    if primary is not None:
        indexer.index_file(primary)
except Exception:
    logger.exception(
        "content indexing failed for book_id=%s; continuing import",
        book.id,
    )
```

Place the block guarded by `if extract_text` (or the equivalent flag) so existing callers that pass `extract_text=False` opt out.

If `logger` is not already defined at module level, add `import logging; logger = logging.getLogger(__name__)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_indexer_on_import.py -q`
Expected: 2 passed.

- [ ] **Step 5: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add book_memex/services/import_service.py tests/test_content_indexer_on_import.py
git commit -m "$(cat <<'EOF'
feat(import): run ContentIndexer after cover extraction

When extract_text=True on add_book, the indexer runs on the primary
file and writes BookContent rows. Extraction failures are logged but
do not abort the import. Unsupported formats are a no-op (no rows).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `book-memex extract <book_id>` CLI command

**Files:**
- Modify: `book_memex/cli.py`
- Create: `tests/test_cli_reindex.py`

A debugging-oriented command: run the indexer on one book's primary file and print the IndexResult.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_reindex.py`:

```python
"""Tests for `book-memex extract` and `book-memex reindex-content` CLI."""
import tempfile
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def tmp_lib_with_book(sample_epub):
    from book_memex.library_db import Library

    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "a.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(dest, metadata={"title": "A", "creators": ["X"]}, extract_text=False)
    lib.close()
    yield temp_dir, book.id
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_extract_single_book(tmp_lib_with_book):
    from book_memex.cli import app

    temp_dir, book_id = tmp_lib_with_book
    runner = CliRunner()
    result = runner.invoke(
        app, ["--library-path", str(temp_dir), "extract", str(book_id)]
    )
    assert result.exit_code == 0
    assert "segments_written" in result.output
    assert "3" in result.output  # 3 chapters in the sample EPUB
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_reindex.py -q -k test_extract_single_book`
Expected: `No such command 'extract'` exit code != 0.

- [ ] **Step 3: Add the command**

Open `book_memex/cli.py`. Locate an appropriate section (e.g., after `rebuild` or near other maintenance commands) and add:

```python
@app.command("extract")
def extract_cmd(
    book_id: int = typer.Argument(..., help="Book ID to extract content for"),
    library_path: Optional[Path] = typer.Option(
        None, "--library-path", "-L", help="Library directory"
    ),
):
    """Run the segment extractor on a single book's primary file."""
    lib = Library.open(resolve_library_path(library_path))
    try:
        book = lib.session.get(Book, book_id)
        if book is None:
            typer.echo(f"Book {book_id} not found", err=True)
            raise typer.Exit(code=1)
        pf = book.primary_file
        if pf is None:
            typer.echo(f"Book {book_id} has no files", err=True)
            raise typer.Exit(code=1)
        from book_memex.services.content_indexer import ContentIndexer
        indexer = ContentIndexer(lib.session, library_path=lib.library_path)
        result = indexer.index_file(pf)
        typer.echo(
            f"status={result.status} "
            f"segments_written={result.segments_written} "
            f"extractor_version={result.extractor_version}"
        )
    finally:
        lib.close()
```

Add any missing imports at the top: `from book_memex.db.models import Book`, `from pathlib import Path`, `import typer`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_reindex.py -q -k test_extract_single_book`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add book_memex/cli.py tests/test_cli_reindex.py
git commit -m "feat(cli): add 'book-memex extract <book_id>' for debugging extraction"
```

---

## Task 12: `book-memex reindex-content` CLI command

**Files:**
- Modify: `book_memex/cli.py`
- Add tests to: `tests/test_cli_reindex.py`

Re-extract content for a single book (`--book <id>`) or for every book with files (`--all`). Useful when upgrading the extractor.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_reindex.py`:

```python
def test_reindex_all(tmp_lib_with_book):
    from book_memex.cli import app

    temp_dir, _ = tmp_lib_with_book
    runner = CliRunner()
    result = runner.invoke(
        app, ["--library-path", str(temp_dir), "reindex-content", "--all"]
    )
    assert result.exit_code == 0
    assert "books_processed=1" in result.output
    assert "segments_written=3" in result.output


def test_reindex_single_book(tmp_lib_with_book):
    from book_memex.cli import app

    temp_dir, book_id = tmp_lib_with_book
    runner = CliRunner()
    result = runner.invoke(
        app, ["--library-path", str(temp_dir), "reindex-content", "--book", str(book_id)]
    )
    assert result.exit_code == 0
    assert "books_processed=1" in result.output


def test_reindex_requires_book_or_all(tmp_lib_with_book):
    from book_memex.cli import app

    temp_dir, _ = tmp_lib_with_book
    runner = CliRunner()
    result = runner.invoke(
        app, ["--library-path", str(temp_dir), "reindex-content"]
    )
    assert result.exit_code != 0
    assert "--book" in result.output or "--all" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_reindex.py -q`
Expected: 3 failures on the new tests.

- [ ] **Step 3: Add the command**

Append to `book_memex/cli.py`:

```python
@app.command("reindex-content")
def reindex_content_cmd(
    book_id: Optional[int] = typer.Option(None, "--book", help="Specific book ID"),
    all_books: bool = typer.Option(False, "--all", help="Reindex every book"),
    library_path: Optional[Path] = typer.Option(
        None, "--library-path", "-L", help="Library directory"
    ),
):
    """Re-extract segment content for one book or the whole library."""
    if not book_id and not all_books:
        typer.echo("error: specify --book <id> or --all", err=True)
        raise typer.Exit(code=2)

    lib = Library.open(resolve_library_path(library_path))
    try:
        from book_memex.services.content_indexer import ContentIndexer
        indexer = ContentIndexer(lib.session, library_path=lib.library_path)

        if all_books:
            books_iter = lib.session.query(Book).all()
        else:
            b = lib.session.get(Book, book_id)
            if b is None:
                typer.echo(f"Book {book_id} not found", err=True)
                raise typer.Exit(code=1)
            books_iter = [b]

        books_processed = 0
        segments_written = 0
        for book in books_iter:
            pf = book.primary_file
            if pf is None:
                continue
            result = indexer.index_file(pf)
            books_processed += 1
            segments_written += result.segments_written

        typer.echo(
            f"books_processed={books_processed} segments_written={segments_written}"
        )
    finally:
        lib.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_reindex.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add book_memex/cli.py tests/test_cli_reindex.py
git commit -m "feat(cli): 'book-memex reindex-content --book <id>|--all'"
```

---

## Task 13: Within-book content search REST endpoint

**Files:**
- Modify: `book_memex/server.py`
- Create: `tests/test_server_content_search.py`

`GET /api/books/{book_id}/search?q=...&limit=50` returns ranked BM25 snippets with anchors and pre-built URI fragments.

- [ ] **Step 1: Write the failing test**

Create `tests/test_server_content_search.py`:

```python
"""Integration tests for /api/books/{id}/search and /api/search/content."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library


@pytest.fixture
def client_with_indexed_book(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "a.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(dest, metadata={"title": "A", "creators": ["X"]}, extract_text=True)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_within_book_search_returns_hits(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=Bayesian")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    top = data[0]
    assert "snippet" in top
    assert "segment_type" in top
    assert "segment_index" in top
    assert "anchor" in top
    assert "fragment" in top
    assert top["fragment"].startswith("epubcfi(") or top["fragment"].startswith("page=")


def test_within_book_search_empty_query_returns_400(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=")
    assert r.status_code == 400


def test_within_book_search_limit(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get(f"/api/books/{book.id}/search?q=a&limit=1")
    assert r.status_code == 200
    assert len(r.json()) <= 1


def test_cross_library_content_search(client_with_indexed_book):
    client, book, _ = client_with_indexed_book
    r = client.get("/api/search/content?q=Bayesian")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    top = data[0]
    assert top["book_id"] == book.id
    assert top["book_uri"].startswith("book-memex://book/")
    assert "fragment" in top


def test_cross_library_search_no_matches_empty(client_with_indexed_book):
    client, _, _ = client_with_indexed_book
    r = client.get("/api/search/content?q=xenomorph_never_present")
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_content_search.py -q`
Expected: 404s.

- [ ] **Step 3: Implement search helpers and endpoints**

Open `book_memex/server.py`. Add imports:

```python
from sqlalchemy import text as _sqltext
from book_memex.core.fts import safe_fts_query
```

Add a response Pydantic model near the other models:

```python
class ContentSearchHit(BaseModel):
    content_id: int
    book_id: int
    book_uri: str
    segment_type: str
    segment_index: int
    title: Optional[str]
    anchor: dict
    fragment: str
    snippet: str
    rank: float
```

Add a helper and two endpoints (position them after the existing `/api/search` metadata endpoint):

```python
def _fragment_for(anchor: dict, segment_type: str) -> str:
    """Build a Book URI fragment from an anchor dict."""
    if segment_type == "chapter" and "cfi" in anchor:
        return anchor["cfi"]
    if segment_type == "page" and "page" in anchor:
        return f"page={anchor['page']}"
    if segment_type == "text" and "offset" in anchor:
        return f"offset={anchor['offset']},length={anchor.get('length', 0)}"
    return ""


def _run_content_search(
    session, fts_query: str, book_id: Optional[int], limit: int,
):
    """Execute an FTS5 MATCH and shape results for API consumption."""
    if book_id is not None:
        sql = _sqltext(
            """
            SELECT
                bc.id,
                f.book_id,
                bk.unique_id AS book_unique_id,
                bc.segment_type,
                bc.segment_index,
                bc.title,
                bc.anchor,
                snippet(book_content_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
                bm25(book_content_fts) AS rank
            FROM book_content_fts
            JOIN book_content bc ON bc.id = book_content_fts.rowid
            JOIN files f ON f.id = bc.file_id
            JOIN books bk ON bk.id = f.book_id
            WHERE book_content_fts MATCH :q
              AND f.book_id = :book_id
              AND bc.archived_at IS NULL
            ORDER BY rank
            LIMIT :limit
            """
        )
        rows = session.execute(sql, {"q": fts_query, "book_id": book_id, "limit": limit}).fetchall()
    else:
        sql = _sqltext(
            """
            SELECT
                bc.id,
                f.book_id,
                bk.unique_id AS book_unique_id,
                bc.segment_type,
                bc.segment_index,
                bc.title,
                bc.anchor,
                snippet(book_content_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
                bm25(book_content_fts) AS rank
            FROM book_content_fts
            JOIN book_content bc ON bc.id = book_content_fts.rowid
            JOIN files f ON f.id = bc.file_id
            JOIN books bk ON bk.id = f.book_id
            WHERE book_content_fts MATCH :q
              AND bc.archived_at IS NULL
            ORDER BY rank
            LIMIT :limit
            """
        )
        rows = session.execute(sql, {"q": fts_query, "limit": limit}).fetchall()

    import json
    hits = []
    for r in rows:
        anchor = r.anchor
        if isinstance(anchor, str):
            try:
                anchor = json.loads(anchor)
            except (TypeError, ValueError):
                anchor = {}
        hits.append({
            "content_id": r.id,
            "book_id": r.book_id,
            "book_uri": f"book-memex://book/{r.book_unique_id}",
            "segment_type": r.segment_type,
            "segment_index": r.segment_index,
            "title": r.title,
            "anchor": anchor,
            "fragment": _fragment_for(anchor, r.segment_type),
            "snippet": r.snippet or "",
            "rank": float(r.rank),
        })
    return hits


@app.get("/api/books/{book_id}/search", response_model=List[ContentSearchHit])
def within_book_search(
    book_id: int,
    q: str,
    limit: int = 50,
    advanced: bool = False,
):
    if not q or not q.strip():
        raise HTTPException(400, "q is required")
    lib = get_library()
    fts_query = safe_fts_query(q, advanced=advanced)
    if not fts_query:
        raise HTTPException(400, "q is required")
    return _run_content_search(lib.session, fts_query, book_id=book_id, limit=limit)


@app.get("/api/search/content", response_model=List[ContentSearchHit])
def cross_library_search(
    q: str,
    limit: int = 50,
    advanced: bool = False,
):
    if not q or not q.strip():
        raise HTTPException(400, "q is required")
    lib = get_library()
    fts_query = safe_fts_query(q, advanced=advanced)
    if not fts_query:
        raise HTTPException(400, "q is required")
    return _run_content_search(lib.session, fts_query, book_id=None, limit=limit)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_content_search.py -q`
Expected: 5 passed.

- [ ] **Step 5: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add book_memex/server.py tests/test_server_content_search.py
git commit -m "$(cat <<'EOF'
feat(api): add /api/books/{id}/search and /api/search/content

Both accept `q` (required) + `limit` + `advanced` flag. Return ranked
(BM25) BookContent hits with snippet, anchor, and a pre-built URI
fragment per result. Empty q returns 400. Archived segments are
excluded by default.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: MCP tools — `search_book_content`, `search_library_content`, `get_segment(s)`

**Files:**
- Modify: `book_memex/mcp/tools.py`
- Modify: `book_memex/mcp/server.py`
- Create: `tests/test_mcp_content_tools.py`

Mirror the REST endpoints plus add RAG-ready pagination (`get_segments`) and point lookup (`get_segment`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_content_tools.py`:

```python
"""Tests for MCP content-search tools."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    search_book_content_impl,
    search_library_content_impl,
    get_segment_impl,
    get_segments_impl,
)


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


def test_search_book_content(lib_indexed):
    lib, book = lib_indexed
    hits = search_book_content_impl(lib.session, book_id=book.id, query="Bayesian")
    assert len(hits) >= 1
    assert hits[0]["segment_type"] == "chapter"
    assert "fragment" in hits[0]


def test_search_library_content(lib_indexed):
    lib, book = lib_indexed
    hits = search_library_content_impl(lib.session, query="quick brown fox")
    assert len(hits) >= 1
    assert hits[0]["book_uri"].startswith("book-memex://book/")


def test_get_segment_by_index(lib_indexed):
    lib, book = lib_indexed
    seg = get_segment_impl(
        lib.session, book_id=book.id, segment_type="chapter", segment_index=0,
    )
    assert seg["segment_index"] == 0
    assert "text" in seg
    assert "Intro" in (seg.get("title") or "") or "Intro" in seg.get("text", "")


def test_get_segments_paginated(lib_indexed):
    lib, book = lib_indexed
    segs = get_segments_impl(lib.session, book_id=book.id, limit=2, offset=0)
    assert len(segs) == 2
    assert [s["segment_index"] for s in segs] == [0, 1]
    more = get_segments_impl(lib.session, book_id=book.id, limit=2, offset=2)
    assert len(more) == 1
    assert more[0]["segment_index"] == 2


def test_search_rejects_empty_query(lib_indexed):
    lib, book = lib_indexed
    with pytest.raises(ValueError):
        search_book_content_impl(lib.session, book_id=book.id, query="")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_content_tools.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement the tool impls**

Add to `book_memex/mcp/tools.py` (below the existing reading tools):

```python
from book_memex.core.fts import safe_fts_query
from book_memex.db.models import BookContent


def _content_row_to_dict(row, *, include_text: bool = False) -> Dict[str, Any]:
    """Shape a BookContent row as a dict for MCP consumption."""
    book_uri = None
    book_id = None
    if row.file and row.file.book:
        book = row.file.book
        book_uri = book.uri
        book_id = book.id
    d = {
        "content_id": row.id,
        "book_id": book_id,
        "book_uri": book_uri,
        "segment_type": row.segment_type,
        "segment_index": row.segment_index,
        "title": row.title,
        "anchor": row.anchor,
        "start_page": row.start_page,
        "end_page": row.end_page,
        "extractor_version": row.extractor_version,
        "extraction_status": row.extraction_status,
    }
    if include_text:
        d["text"] = row.content
    return d


def _content_fragment(anchor: Any, segment_type: str) -> str:
    if not isinstance(anchor, dict):
        return ""
    if segment_type == "chapter" and "cfi" in anchor:
        return anchor["cfi"]
    if segment_type == "page" and "page" in anchor:
        return f"page={anchor['page']}"
    if segment_type == "text" and "offset" in anchor:
        return f"offset={anchor['offset']},length={anchor.get('length', 0)}"
    return ""


def search_book_content_impl(
    session: Session, *, book_id: int, query: str,
    limit: int = 20, advanced: bool = False,
) -> List[Dict[str, Any]]:
    """FTS5 search within a single book. Returns ranked snippets with anchors."""
    if not query or not query.strip():
        raise ValueError("query is required")
    fts_query = safe_fts_query(query, advanced=advanced)
    if not fts_query:
        raise ValueError("query resolves to empty FTS5 expression")
    sql = text(
        """
        SELECT
            bc.id,
            f.book_id,
            bk.unique_id AS book_unique_id,
            bc.segment_type,
            bc.segment_index,
            bc.title,
            bc.anchor,
            snippet(book_content_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
            bm25(book_content_fts) AS rank
        FROM book_content_fts
        JOIN book_content bc ON bc.id = book_content_fts.rowid
        JOIN files f ON f.id = bc.file_id
        JOIN books bk ON bk.id = f.book_id
        WHERE book_content_fts MATCH :q
          AND f.book_id = :book_id
          AND bc.archived_at IS NULL
        ORDER BY rank
        LIMIT :limit
        """
    )
    rows = session.execute(sql, {"q": fts_query, "book_id": book_id, "limit": limit}).fetchall()
    import json
    hits = []
    for r in rows:
        anchor = r.anchor
        if isinstance(anchor, str):
            try:
                anchor = json.loads(anchor)
            except (TypeError, ValueError):
                anchor = {}
        hits.append({
            "content_id": r.id,
            "book_id": r.book_id,
            "book_uri": f"book-memex://book/{r.book_unique_id}",
            "segment_type": r.segment_type,
            "segment_index": r.segment_index,
            "title": r.title,
            "anchor": anchor,
            "fragment": _content_fragment(anchor, r.segment_type),
            "snippet": r.snippet or "",
            "rank": float(r.rank),
        })
    return hits


def search_library_content_impl(
    session: Session, *, query: str, limit: int = 20, advanced: bool = False,
) -> List[Dict[str, Any]]:
    """FTS5 search across every book. Same shape as search_book_content_impl."""
    if not query or not query.strip():
        raise ValueError("query is required")
    fts_query = safe_fts_query(query, advanced=advanced)
    if not fts_query:
        raise ValueError("query resolves to empty FTS5 expression")
    sql = text(
        """
        SELECT
            bc.id,
            f.book_id,
            bk.unique_id AS book_unique_id,
            bc.segment_type,
            bc.segment_index,
            bc.title,
            bc.anchor,
            snippet(book_content_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
            bm25(book_content_fts) AS rank
        FROM book_content_fts
        JOIN book_content bc ON bc.id = book_content_fts.rowid
        JOIN files f ON f.id = bc.file_id
        JOIN books bk ON bk.id = f.book_id
        WHERE book_content_fts MATCH :q
          AND bc.archived_at IS NULL
        ORDER BY rank
        LIMIT :limit
        """
    )
    rows = session.execute(sql, {"q": fts_query, "limit": limit}).fetchall()
    import json
    hits = []
    for r in rows:
        anchor = r.anchor
        if isinstance(anchor, str):
            try:
                anchor = json.loads(anchor)
            except (TypeError, ValueError):
                anchor = {}
        hits.append({
            "content_id": r.id,
            "book_id": r.book_id,
            "book_uri": f"book-memex://book/{r.book_unique_id}",
            "segment_type": r.segment_type,
            "segment_index": r.segment_index,
            "title": r.title,
            "anchor": anchor,
            "fragment": _content_fragment(anchor, r.segment_type),
            "snippet": r.snippet or "",
            "rank": float(r.rank),
        })
    return hits


def get_segment_impl(
    session: Session, *, book_id: int, segment_type: str, segment_index: int,
) -> Dict[str, Any]:
    """Fetch one BookContent row by (book, type, index). Raises LookupError."""
    row = (
        session.query(BookContent)
        .join(BookContent.file)
        .filter(
            BookContent.segment_type == segment_type,
            BookContent.segment_index == segment_index,
        )
        .filter(BookContent.file.has(book_id=book_id))
        .first()
    )
    if row is None:
        raise LookupError(
            f"segment not found: book_id={book_id} type={segment_type} index={segment_index}"
        )
    return _content_row_to_dict(row, include_text=True)


def get_segments_impl(
    session: Session, *, book_id: int, limit: int = 50, offset: int = 0,
) -> List[Dict[str, Any]]:
    """Paginated RAG-ready surface: ordered segments for a book with full text."""
    rows = (
        session.query(BookContent)
        .join(BookContent.file)
        .filter(BookContent.file.has(book_id=book_id))
        .filter(BookContent.archived_at.is_(None))
        .order_by(BookContent.segment_index)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_content_row_to_dict(r, include_text=True) for r in rows]
```

- [ ] **Step 4: Register tools in `mcp/server.py`**

Append to `create_mcp_server` after the existing reading tools:

```python
    from book_memex.mcp.tools import (
        search_book_content_impl, search_library_content_impl,
        get_segment_impl, get_segments_impl,
    )

    @mcp.tool(
        name="search_book_content",
        description=(
            "FTS5 search within a single book. Returns ranked snippets with "
            "an anchor and a pre-built URI fragment. Safe against FTS5 operator "
            "injection by default (advanced=True opts into raw FTS5 syntax)."
        ),
    )
    def search_book_content(
        book_id: int, query: str, limit: int = 20, advanced: bool = False,
    ) -> list:
        return search_book_content_impl(
            library.session, book_id=book_id, query=query,
            limit=limit, advanced=advanced,
        )

    @mcp.tool(
        name="search_library_content",
        description=(
            "FTS5 search across every book. Same response shape as "
            "search_book_content; results include book_uri per hit."
        ),
    )
    def search_library_content(
        query: str, limit: int = 20, advanced: bool = False,
    ) -> list:
        return search_library_content_impl(
            library.session, query=query, limit=limit, advanced=advanced,
        )

    @mcp.tool(
        name="get_segment",
        description=(
            "Fetch one BookContent row by (book_id, segment_type, segment_index). "
            "Returns the full segment text, anchor, and extractor version."
        ),
    )
    def get_segment(book_id: int, segment_type: str, segment_index: int) -> dict:
        return get_segment_impl(
            library.session, book_id=book_id,
            segment_type=segment_type, segment_index=segment_index,
        )

    @mcp.tool(
        name="get_segments",
        description=(
            "Paginated RAG-ready access: return segments for a book with full "
            "text, ordered by segment_index. Use limit + offset to paginate."
        ),
    )
    def get_segments(book_id: int, limit: int = 50, offset: int = 0) -> list:
        return get_segments_impl(
            library.session, book_id=book_id, limit=limit, offset=offset,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_mcp_content_tools.py -q`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add book_memex/mcp/tools.py book_memex/mcp/server.py tests/test_mcp_content_tools.py
git commit -m "$(cat <<'EOF'
feat(mcp): search_book_content, search_library_content, get_segment(s)

Four new tools covering within-book FTS5 search, cross-library search,
single-segment lookup, and paginated RAG surface (get_segments with
limit/offset returns ordered segments including full text).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `ask_book` MCP tool (FTS5 + LLM)

**Files:**
- Create: `book_memex/services/ask_book.py`
- Modify: `book_memex/mcp/tools.py`
- Modify: `book_memex/mcp/server.py`
- Create: `tests/test_ask_book.py`

Retrieves top-k segments via FTS5, builds a prompt with citation markers, calls a configured LLM, parses citations from the response. v1 uses the raw question as the FTS5 query (no pre-LLM keyword extraction). LLM is pluggable via a callable injected at construction time so tests can use a mock.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ask_book.py`:

```python
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
        lib.session, book_id=book.id, question="What does the book say about Bayesian inference?",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ask_book.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement `ask_book`**

Create `book_memex/services/ask_book.py`:

```python
"""ask_book: FTS5 retrieval + LLM answer for a single book.

v1 scope: the raw question is run through safe_fts_query and sent to
FTS5 for top-k retrieval. No pre-LLM keyword extraction (deferred). The
LLM is a pluggable callable so tests can mock it. A null/missing LLM
returns a structured "no LLM configured" message instead of raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from book_memex.core.fts import safe_fts_query
from book_memex.mcp.tools import search_book_content_impl


LLM = Callable[..., str]


@dataclass
class AskBookResult:
    answer: Optional[str]
    citations: List[Dict[str, Any]] = field(default_factory=list)
    segments_used: List[Dict[str, Any]] = field(default_factory=list)
    message: Optional[str] = None


# Match both bare and bracketed URI forms in LLM output.
_CITATION_RE = re.compile(
    r"book-memex://book/[^\s\]\)#]+(?:#[^\s\]\)]+)?"
)


def ask_book(
    session: Session,
    *,
    book_id: int,
    question: str,
    k: int = 8,
    llm: Optional[LLM] = None,
) -> AskBookResult:
    """Retrieve top-k segments from one book and ask the LLM to answer."""
    if not question or not question.strip():
        return AskBookResult(answer=None, message="question is required")

    if llm is None:
        return AskBookResult(
            answer=None,
            message="no LLM configured; pass llm=... or set BOOK_MEMEX_LLM env",
        )

    hits = search_book_content_impl(
        session, book_id=book_id, query=question, limit=k,
    )
    if not hits:
        return AskBookResult(
            answer=None,
            message="no matching content; try a different query or reindex the book",
        )

    prompt = _build_prompt(question, hits)
    try:
        raw = llm(prompt)
    except Exception as exc:
        return AskBookResult(
            answer=None,
            message=f"llm error: {exc}",
            segments_used=hits,
        )

    citations = _parse_citations(raw or "")
    return AskBookResult(
        answer=raw,
        citations=citations,
        segments_used=hits,
    )


def _build_prompt(question: str, hits: List[Dict[str, Any]]) -> str:
    parts = [
        "You are answering a question about a single book. Ground every claim "
        "in the passages below and cite using the book-memex URIs.",
        "",
        f"Question: {question}",
        "",
        "Passages:",
    ]
    for h in hits:
        uri = h["book_uri"]
        frag = h.get("fragment") or ""
        cite = f"{uri}#{frag}" if frag else uri
        snippet = h.get("snippet") or ""
        title = h.get("title") or h.get("segment_type", "")
        parts.append(f"[{cite}] ({title}): {snippet}")
    parts.append("")
    parts.append(
        "Answer the question using only the passages above. "
        "Include at least one citation of the form "
        "`book-memex://book/<id>#<anchor>` for each claim."
    )
    return "\n".join(parts)


def _parse_citations(text: str) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for match in _CITATION_RE.finditer(text):
        uri = match.group(0)
        if uri in seen:
            continue
        seen.add(uri)
        frag = None
        if "#" in uri:
            base, _, frag = uri.partition("#")
        else:
            base = uri
        out.append({"uri": uri, "base": base, "fragment": frag})
    return out
```

- [ ] **Step 4: Expose as MCP tool**

Append to `book_memex/mcp/tools.py`:

```python
from book_memex.services.ask_book import ask_book as _ask_book, AskBookResult


def ask_book_impl(
    session: Session, *, book_id: int, question: str,
    k: int = 8, model: Optional[str] = None,
) -> Dict[str, Any]:
    """FTS5 + LLM answer for a single book. Returns answer, citations, segments_used."""
    llm = _resolve_llm(model)
    result = _ask_book(
        session, book_id=book_id, question=question, k=k, llm=llm,
    )
    return {
        "answer": result.answer,
        "citations": result.citations,
        "segments_used": result.segments_used,
        "message": result.message,
    }


def _resolve_llm(model: Optional[str]):
    """Resolve an LLM callable from env/config. Returns None if not configured."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    default_model = model or os.environ.get("BOOK_MEMEX_LLM", "claude-sonnet-4-6")

    def _call(prompt: str, **kwargs) -> str:
        resp = client.messages.create(
            model=default_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic response is a list of content blocks; concatenate text.
        return "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )

    return _call
```

And register in `book_memex/mcp/server.py`:

```python
    from book_memex.mcp.tools import ask_book_impl

    @mcp.tool(
        name="ask_book",
        description=(
            "Ask a natural-language question about one book. Uses FTS5 to "
            "retrieve the top-k relevant segments, then asks the configured "
            "LLM to answer grounded in those segments. Response includes "
            "`answer` text, structured `citations` parsed from the answer, "
            "and `segments_used` with full URIs. Returns a `message` (not "
            "an answer) if no LLM is configured or no segments match."
        ),
    )
    def ask_book(book_id: int, question: str, k: int = 8, model: str | None = None) -> dict:
        return ask_book_impl(
            library.session, book_id=book_id, question=question, k=k, model=model,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ask_book.py -q`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add book_memex/services/ask_book.py book_memex/mcp/tools.py book_memex/mcp/server.py tests/test_ask_book.py
git commit -m "$(cat <<'EOF'
feat(mcp): ask_book via FTS5 retrieval + pluggable LLM

Top-k FTS5 segments feed a prompt with URI-tagged citations. LLM
callable is injectable for testing; the default resolves to an
Anthropic client when ANTHROPIC_API_KEY is set and the SDK is
installed, otherwise returns a structured "no LLM configured"
message. Citations are parsed out of the LLM response via regex.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Phase 2 end-to-end integration test

**Files:**
- Create: `tests/test_phase2_e2e.py`

Import a book, verify content is indexed, run within-book search via REST, run ask_book via MCP with a mocked LLM, verify the whole pipeline works.

- [ ] **Step 1: Write the test**

Create `tests/test_phase2_e2e.py`:

```python
"""Phase 2 end-to-end test covering extraction + search + ask_book."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library
from book_memex.mcp.tools import (
    ask_book_impl, search_library_content_impl, get_segments_impl,
)


@pytest.fixture
def e2e_env(sample_epub):
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    dest = lib.library_path / "book.epub"
    shutil.copy(sample_epub, dest)
    book = lib.add_book(
        dest,
        metadata={"title": "Phase 2 Test", "creators": ["Author"]},
        extract_text=True,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_indexes_content_search_and_ask(e2e_env):
    client, book, lib = e2e_env

    # 1. Content was indexed on import.
    segs = get_segments_impl(lib.session, book_id=book.id)
    assert len(segs) == 3
    assert segs[0]["segment_type"] == "chapter"

    # 2. Within-book search via REST returns at least one hit for a chapter term.
    r = client.get(f"/api/books/{book.id}/search?q=Bayesian")
    assert r.status_code == 200
    hits = r.json()
    assert any("Bayesian" in (h.get("title") or "") or "Bayesian" in h["snippet"] for h in hits)

    # 3. Cross-library search via MCP finds the same content.
    lib_hits = search_library_content_impl(lib.session, query="Bayesian")
    assert len(lib_hits) >= 1
    assert lib_hits[0]["book_id"] == book.id

    # 4. ask_book via MCP with a stub LLM that echoes the prompt.
    def fake_llm(prompt: str, **kw) -> str:
        return (
            "The book discusses Bayesian inference. "
            f"See {lib_hits[0]['book_uri']}#{lib_hits[0]['fragment']}."
        )

    # Inject by monkey-patching the resolver so ask_book_impl uses fake_llm.
    from book_memex.mcp import tools as _tools
    original = _tools._resolve_llm
    _tools._resolve_llm = lambda model: fake_llm
    try:
        answer = ask_book_impl(
            lib.session, book_id=book.id,
            question="What does the book say about Bayesian inference?",
        )
    finally:
        _tools._resolve_llm = original

    assert answer["answer"] is not None
    assert "Bayesian" in answer["answer"]
    assert len(answer["segments_used"]) >= 1
    assert len(answer["citations"]) >= 1
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_phase2_e2e.py -q`
Expected: 1 passed.

- [ ] **Step 3: Run the full suite and check coverage**

Run: `pytest -q --tb=no 2>&1 | tail -3`
Expected: no regressions.

Run: `pytest --cov=book_memex --cov-report=term-missing 2>&1 | tail -20`
Expected: Phase 2 modules (`core/fts`, `services/content_extraction/*`, `services/content_indexer`, `services/ask_book`) at 85%+ coverage. `mcp/tools.py` with the new content + ask_book functions remains at 80%+.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase2_e2e.py
git commit -m "$(cat <<'EOF'
test: add phase-2 end-to-end integration test

Covers the full chain: import EPUB -> ContentIndexer writes
BookContent rows -> FTS5 index via triggers -> within-book search
(REST) and cross-library search (MCP) -> ask_book via MCP with a
monkey-patched stub LLM.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

After implementing all tasks, verify against the spec's Phase 2 scope (`docs/superpowers/specs/2026-04-15-book-memex-v1-design.md` §5-7 and §15.1):

1. **Migration 11** (rename text_chunks, drop has_embedding, add refined columns): Task 1. ✓
2. **ORM BookContent** with URI-free segments, archived_at: Task 2. ✓
3. **Migration 12 FTS5**: Task 3. ✓
4. **safe_fts_query**: Task 4. ✓
5. **Content extractors** (EPUB, PDF, TXT): Tasks 5-8. ✓
6. **Extraction wiring into import**: Task 10. ✓
7. **extract + reindex-content CLI**: Tasks 11-12. ✓
8. **Within-book + cross-library search REST**: Task 13. ✓
9. **Content search MCP tools** (search_book_content, search_library_content): Task 14. ✓
10. **RAG surface** (get_segment, get_segments): Task 14. ✓
11. **ask_book MCP tool**: Task 15. ✓
12. **Soft-delete propagation on BookContent**: archived_at column (Task 1) and `WHERE archived_at IS NULL` in search (Task 13, 14). ✓
13. **E2E integration test**: Task 16. ✓

Placeholder scan: no "TBD" / "implement later" / "similar to Task N" patterns. Every code step has actual code.

Type consistency: `Segment` dataclass (Task 5) field names match `BookContent` columns (Task 2), which match the dict shape returned by `_content_row_to_dict` (Task 14), which matches the REST response shape (Task 13). `AskBookResult` fields (Task 15) map to the MCP response dict.

## Notes for the executing agent

- Every task ends with a commit. Do not batch commits across tasks.
- Use the established Phase 1 fixtures (`sample_epub`, `sample_pdf`) shared via `tests/conftest.py`.
- `safe_fts_query` is used by both REST (server.py) and MCP (tools.py) — import it consistently.
- Anchor JSON may round-trip through SQLite as `str`; the search helpers handle both cases with a `json.loads` fallback.
- Preserve the `TextChunk = BookContent` alias in models.py until at least one release cycle after v1.
- When touching `server.py`, keep the flat `@app.<method>(...)` pattern established in Phase 1; do not introduce `APIRouter` sub-mounts.
- When touching `cli.py`, match the existing Typer decorator style and reuse `resolve_library_path()`.
- LLM integration is opt-in. No test should require an Anthropic API key; `test_ask_book.py` passes a mock `llm` callable and `test_phase2_e2e.py` monkey-patches `_resolve_llm`.

## Estimated effort

| Component | Python LOC | Tests LOC |
|---|---|---|
| Migration 11 + 12 | 150 | 250 |
| BookContent ORM | 50 | 50 |
| safe_fts_query | 40 | 80 |
| Extractor interface | 80 | 50 |
| EpubExtractor | 70 | 80 |
| PdfExtractor | 60 | 100 |
| TxtExtractor | 30 | 30 |
| ContentIndexer | 130 | 150 |
| Import wiring | 20 | 80 |
| CLI (extract + reindex) | 90 | 100 |
| Search endpoints (REST) | 170 | 150 |
| MCP content tools | 250 | 150 |
| ask_book | 140 | 150 |
| E2E test | 0 | 90 |
| **Total** | **~1280** | **~1510** |

Roughly 1-2 weeks of focused work. Extractor quality on real-world books is the primary iteration risk.
