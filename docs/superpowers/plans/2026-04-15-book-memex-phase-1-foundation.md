# book-memex Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `ebk` to `book-memex`, add URI-addressability and soft-delete to existing records (Marginalia, ReadingSession, PersonalMetadata), expose marginalia + reading state via REST and MCP, and extend arkiv export. This is Phase 1 of the three-phase book-memex v1 rollout defined in `docs/superpowers/specs/2026-04-15-book-memex-v1-design.md` §15.1. Phase 2 (content extraction + search + `ask_book`) and Phase 3 (browser reader) are separate plans.

**Architecture:** Extend existing ebk data model rather than duplicating. Marginalia already unifies highlights + notes via scope derivation. ReadingSession exists with academic-session fields. Add `uuid` + `archived_at` columns to make records URI-addressable and soft-deletable, add `color` + `anchors` + `progress_anchor` for reader use cases, and add service layer + REST + MCP endpoints. No content extraction or reader UI in this phase.

**Tech Stack:** Python 3.12+, SQLAlchemy, FastAPI, FastMCP (stdio), Typer, pytest, sqlite3 (WAL + FTS5). See `/home/spinoza/github/memex/ebk/` for the codebase.

**Pre-flight note:** All tasks assume the working directory is `/home/spinoza/github/memex/ebk/`. Tests are run via `pytest`. Installation: `pip install -e ".[dev]"`. The existing Makefile has `make test`, `make lint`, etc.

---

## Task 1: Rename Python package `ebk` → `book_memex`

**Files:**
- Move: `ebk/` (top-level Python package) → `book_memex/`
- Modify: `pyproject.toml`
- Modify: every Python file with `from ebk` or `import ebk` (bulk replace)
- Modify: `tests/` (all imports and fixture references)
- Modify: `README.md` (user-facing references)

This is the largest mechanical change. Do it first to reduce churn on later tasks. After this task, the package is `book_memex`, CLI entrypoint is `book-memex`, MCP server identity is `book-memex`, and the existing test suite passes unchanged.

- [ ] **Step 1: Confirm starting state is clean**

Run: `git status`
Expected: `working tree clean` on the current branch. If not clean, commit or stash before proceeding.

- [ ] **Step 2: Rename the package directory**

Run:
```bash
git mv ebk book_memex
```

This preserves git history for each file. Expected: every tracked file under `ebk/` is now under `book_memex/`.

- [ ] **Step 3: Bulk-replace imports across all Python files**

Run:
```bash
# Replace "from ebk." and "from ebk " and "import ebk" at the start of lines/statements.
grep -rl --include='*.py' -E '(from ebk\.|from ebk import|import ebk$|import ebk\.|import ebk )' . \
  | xargs sed -i -E \
    -e 's/from ebk\./from book_memex./g' \
    -e 's/from ebk import/from book_memex import/g' \
    -e 's/^import ebk$/import book_memex/g' \
    -e 's/^import ebk\./import book_memex./g' \
    -e 's/^import ebk /import book_memex /g'
```

- [ ] **Step 4: Update `pyproject.toml`**

Open `pyproject.toml`. Make these edits:

Replace `name = "ebk"` with `name = "book-memex"`.

Replace the entrypoints block. If the current block reads:

```toml
[project.scripts]
ebk = "ebk.cli:app"
ebk-mcp-serve = "ebk.mcp.server:run_server"
```

Change it to:

```toml
[project.scripts]
book-memex = "book_memex.cli:app"
book-memex-mcp-serve = "book_memex.mcp.server:run_server"
ebk = "book_memex.cli:app"                       # deprecated alias, one release
ebk-mcp-serve = "book_memex.mcp.server:run_server"   # deprecated alias, one release
```

If `[tool.setuptools.packages.find]` or `[tool.hatch.build.targets.wheel]` pins `ebk` as the package, update it to `book_memex`.

Update the `description` field to mention "book-memex" instead of "ebk" if present.

- [ ] **Step 5: Search for residual "ebk" string references and update the user-visible ones**

Run:
```bash
grep -rn --include='*.py' -E '\bebk\b' . | grep -v -E '\.venv|__pycache__|node_modules|\.git' | head -80
```

Review each match. Update:
- Docstrings that refer to "ebk" by name, changing them to "book-memex".
- Log messages and CLI help text.
- MCP server name: in `book_memex/mcp/server.py`, change `FastMCP("ebk", ...)` to `FastMCP("book-memex", ...)`. Update the `instructions` string to mention "book-memex".
- Any hard-coded database path components that contain "ebk" (unlikely, but check).

Do NOT change: comments that describe historical context, string fragments inside SQL migration names that refer to past migrations, or fixture data that intentionally includes legacy names.

- [ ] **Step 6: Update `README.md`**

Replace user-facing "ebk" references with "book-memex" (package name, CLI commands). Keep the historical name in a single "Renamed from ebk (previous name)" note near the top of the README.

- [ ] **Step 7: Add the `ebk` deprecation shim**

Create `book_memex/_ebk_alias.py`:

```python
"""Deprecation shim for the old `ebk` CLI entrypoint.

Prints a one-time deprecation notice and forwards to the book-memex CLI.
This alias is scheduled for removal in the release after v1.
"""
import sys
import warnings

from book_memex.cli import app


def main():
    warnings.warn(
        "The `ebk` command has been renamed to `book-memex`. "
        "`ebk` will be removed in the release after v1. "
        "Update your scripts and configs to use `book-memex`.",
        DeprecationWarning,
        stacklevel=2,
    )
    print(
        "[DEPRECATED] `ebk` is now `book-memex`. Use `book-memex` going forward.",
        file=sys.stderr,
    )
    app()
```

Update `pyproject.toml` `[project.scripts]` so the `ebk` alias points to this shim:

```toml
ebk = "book_memex._ebk_alias:main"
ebk-mcp-serve = "book_memex.mcp.server:run_server"
```

- [ ] **Step 8: Reinstall editable**

Run:
```bash
pip install -e ".[dev]"
```
Expected: no errors. Both `book-memex` and `ebk` commands should resolve.

Verify:
```bash
which book-memex
which ebk
```
Expected: both print paths to scripts inside the active virtualenv.

- [ ] **Step 9: Run the existing test suite**

Run:
```bash
pytest -q
```
Expected: all existing tests pass (no code logic changed, only names). If any tests fail, the most likely cause is a missed `from ebk` import or a hardcoded `ebk` string in a fixture. Fix and rerun.

- [ ] **Step 10: Commit**

Run:
```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: rename ebk package to book_memex

- Move ebk/ -> book_memex/ (git mv to preserve history)
- Bulk-replace imports across Python sources and tests
- Update pyproject.toml name, description, scripts
- Add `ebk` CLI alias with deprecation notice (to be removed post-v1)
- Rename MCP server identity from "ebk" to "book-memex"
- Preserve all existing test behavior; no logic changes

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add URI builder/parser module

**Files:**
- Create: `book_memex/core/__init__.py` (if `core/` package does not yet exist)
- Create: `book_memex/core/uri.py`
- Create: `tests/test_uri.py`

URIs are the contract between book-memex and the federation layer. This module is a pure helper with no SQLAlchemy dependency.

- [ ] **Step 1: Write the failing test file**

Create `tests/test_uri.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_uri.py -q
```
Expected: `ImportError: No module named 'book_memex.core.uri'` or similar — the module does not exist yet.

- [ ] **Step 3: Create the core package stub**

Create `book_memex/core/__init__.py` with a single-line docstring:
```python
"""Core utilities (URIs, soft-delete helpers) with no ORM dependency."""
```

- [ ] **Step 4: Implement the URI module**

Create `book_memex/core/uri.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_uri.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/core/__init__.py book_memex/core/uri.py tests/test_uri.py
git commit -m "$(cat <<'EOF'
feat(core): add URI builder/parser for book-memex scheme

Public surface: book, marginalia, reading kinds plus URI fragments
for positions within a Book. Pure Python, no ORM dependency.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Migration 9 — add `archived_at` to existing tables

**Files:**
- Modify: `book_memex/db/migrations.py`
- Create: `tests/test_migration_9_archived_at.py`

Add `archived_at TIMESTAMP NULL` column to these tables: `books`, `authors`, `subjects`, `tags`, `files`, `covers`, `personal_metadata`, `marginalia`, `reading_sessions`. SQLite `ALTER TABLE ... ADD COLUMN` is trivial (no row rewrite). Bump schema version to 9.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_9_archived_at.py`:

```python
"""Test migration 9: add archived_at to existing tables."""
import tempfile
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from book_memex.db.migrations import (
    migrate_add_archived_at,
    get_schema_version,
    CURRENT_SCHEMA_VERSION,
)
from book_memex.library_db import Library


SOFT_DELETE_TABLES = [
    "books", "authors", "subjects", "tags",
    "files", "covers", "personal_metadata",
    "marginalia", "reading_sessions",
]


@pytest.fixture
def fresh_library():
    """A freshly initialized library (already at latest schema)."""
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_current_schema_version_is_9_or_later(fresh_library):
    lib, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    assert get_schema_version(engine) >= 9
    assert CURRENT_SCHEMA_VERSION >= 9


def test_every_soft_delete_table_has_archived_at(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table)}
        assert "archived_at" in cols, f"{table} is missing archived_at column"


def test_archived_at_is_nullable(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert cols["archived_at"]["nullable"] is True, \
            f"{table}.archived_at should be nullable"


def test_migration_is_idempotent(fresh_library):
    """Running the migration twice is a no-op, not an error."""
    lib, temp_dir = fresh_library
    # Second application should be a no-op (already applied).
    applied = migrate_add_archived_at(temp_dir)
    assert applied in (True, False)  # either is acceptable for a re-run
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_migration_9_archived_at.py -q
```
Expected: `ImportError` on `migrate_add_archived_at` or `AssertionError` because the columns do not yet exist.

- [ ] **Step 3: Implement the migration**

Open `book_memex/db/migrations.py`. Add a new migration function before the `MIGRATIONS` list:

```python
def migrate_add_archived_at(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 9: add archived_at TIMESTAMP NULL to soft-deletable tables.

    Tables: books, authors, subjects, tags, files, covers, personal_metadata,
    marginalia, reading_sessions. New column defaults to NULL (= not archived).
    """
    name = "add_archived_at"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        logger.debug(f"Migration {name} already applied")
        return False

    tables = [
        "books", "authors", "subjects", "tags",
        "files", "covers", "personal_metadata",
        "marginalia", "reading_sessions",
    ]

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if dry_run:
        logger.info(f"DRY RUN: would add archived_at to: {tables}")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        for table in tables:
            if table not in existing_tables:
                logger.debug(f"  skipping {table}: table does not exist")
                continue
            # SQLite is happy to add a nullable column with no default.
            # Check that the column is not already there (defensive).
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "archived_at" in cols:
                logger.debug(f"  skipping {table}: archived_at already present")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN archived_at TIMESTAMP NULL"))
            logger.debug(f"  added archived_at to {table}")

    record_migration(engine, version=9, migration_name=name)
    return True
```

Update the `MIGRATIONS` list at the bottom of the file to include the new entry as the next tuple:

```python
MIGRATIONS = [
    # ... existing tuples ...
    (9, "add_archived_at", migrate_add_archived_at),
]
```

Update the constant:

```python
CURRENT_SCHEMA_VERSION = 9
```

- [ ] **Step 4: Verify `Library.open()` applies migrations on init**

Open `book_memex/db/session.py` (or `book_memex/library_db.py`, wherever init is). Confirm that when a new library is opened, pending migrations are run (likely via `run_all_migrations` or an equivalent startup call). If not, trace the init flow and ensure the new migration runs on `Library.open()`.

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_migration_9_archived_at.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Run the full test suite to catch regressions**

Run:
```bash
pytest -q
```
Expected: all existing tests still pass. The new column is nullable and unqueried by existing code, so no impact.

- [ ] **Step 7: Commit**

Run:
```bash
git add book_memex/db/migrations.py tests/test_migration_9_archived_at.py
git commit -m "$(cat <<'EOF'
feat(db): migration 9 - add archived_at to soft-deletable tables

Adds nullable TIMESTAMP column to: books, authors, subjects, tags,
files, covers, personal_metadata, marginalia, reading_sessions.
No data migration; existing rows have NULL = not archived.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Migration 10 — add `uuid`, `color`, anchors, `progress_anchor`

**Files:**
- Modify: `book_memex/db/migrations.py`
- Create: `tests/test_migration_10_uri_columns.py`

Add the columns that make records URI-addressable (`uuid`) and support reader features (`color`, `start_anchor`, `end_anchor`, `progress_anchor`). Backfill `uuid` for existing rows using `uuid4().hex`. Unique index on each new `uuid`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_10_uri_columns.py`:

```python
"""Test migration 10: uuid + color + anchors + progress_anchor."""
import tempfile
import shutil
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from book_memex.db.models import Base, Book, Marginalia, ReadingSession, PersonalMetadata
from book_memex.library_db import Library


UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def fresh_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib, temp_dir
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_marginalia_has_uuid_color_archived_at(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("marginalia")}
    assert {"uuid", "color", "archived_at"}.issubset(cols)


def test_reading_sessions_has_uuid_anchors(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("reading_sessions")}
    assert {"uuid", "start_anchor", "end_anchor", "archived_at"}.issubset(cols)


def test_personal_metadata_has_progress_anchor(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    cols = {c["name"] for c in inspect(engine).get_columns("personal_metadata")}
    assert "progress_anchor" in cols


def test_marginalia_uuid_unique_index(fresh_library):
    _, temp_dir = fresh_library
    engine = create_engine(f"sqlite:///{temp_dir}/library.db")
    with engine.begin() as conn:
        # Attempting two rows with the same UUID should fail.
        conn.execute(text("""
            INSERT INTO marginalia (uuid, content, created_at, updated_at)
            VALUES ('dup', 'a', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        with pytest.raises(Exception):
            conn.execute(text("""
                INSERT INTO marginalia (uuid, content, created_at, updated_at)
                VALUES ('dup', 'b', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))


def test_existing_marginalia_rows_get_uuid_backfill():
    """Simulate: a pre-migration library with marginalia rows. After migration, each has a UUID."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Stage 1: create a library and a Marginalia row via the ORM
        lib = Library.open(temp_dir)
        # Create via raw SQL to simulate a pre-migration-10 row (no uuid).
        # But since migrations run at open(), the row we insert now will have uuid.
        # Instead, null-out the uuid to simulate legacy state, then re-run migration.
        with lib.session.begin():
            lib.session.execute(text(
                "INSERT INTO marginalia (content, created_at, updated_at) VALUES ('x', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            mid = lib.session.execute(text("SELECT last_insert_rowid()")).scalar()
            lib.session.execute(text("UPDATE marginalia SET uuid = NULL WHERE id = :i"), {"i": mid})
        lib.close()

        # Stage 2: re-run migration (should backfill)
        from book_memex.db.migrations import migrate_add_uri_columns
        migrate_add_uri_columns(temp_dir)

        # Stage 3: verify
        lib = Library.open(temp_dir)
        row = lib.session.execute(text(
            f"SELECT uuid FROM marginalia WHERE id = {mid}"
        )).scalar()
        lib.close()
        assert row is not None
        assert UUID_HEX_RE.match(row), f"expected 32-hex UUID, got {row!r}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_migration_10_uri_columns.py -q
```
Expected: import error or failing assertions (columns don't exist).

- [ ] **Step 3: Implement the migration**

In `book_memex/db/migrations.py`, add:

```python
def migrate_add_uri_columns(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 10: add uuid + color + anchors + progress_anchor.

    - Marginalia: uuid (UNIQUE), color
    - ReadingSession: uuid (UNIQUE), start_anchor (JSON), end_anchor (JSON)
    - PersonalMetadata: progress_anchor (JSON)

    Existing rows get their uuid backfilled with uuid4().hex.
    """
    import uuid as _uuid

    name = "add_uri_columns"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        # Even if the migration record is present, backfill any NULL uuids
        # (defensive; this handles partial or hand-edited prior states).
        with engine.begin() as conn:
            _backfill_uuids(conn, _uuid)
        return False

    if dry_run:
        logger.info("DRY RUN: would add uuid, color, anchors, progress_anchor")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        inspector = inspect(engine)

        # Marginalia: uuid, color
        mcols = {c["name"] for c in inspector.get_columns("marginalia")}
        if "uuid" not in mcols:
            conn.execute(text("ALTER TABLE marginalia ADD COLUMN uuid VARCHAR(36)"))
        if "color" not in mcols:
            conn.execute(text("ALTER TABLE marginalia ADD COLUMN color VARCHAR(7)"))

        # ReadingSession: uuid, start_anchor, end_anchor
        rcols = {c["name"] for c in inspector.get_columns("reading_sessions")}
        if "uuid" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN uuid VARCHAR(36)"))
        if "start_anchor" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN start_anchor JSON"))
        if "end_anchor" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN end_anchor JSON"))

        # PersonalMetadata: progress_anchor
        pcols = {c["name"] for c in inspector.get_columns("personal_metadata")}
        if "progress_anchor" not in pcols:
            conn.execute(text("ALTER TABLE personal_metadata ADD COLUMN progress_anchor JSON"))

        # Backfill UUIDs for existing rows
        _backfill_uuids(conn, _uuid)

        # Unique indexes on uuid (partial to allow NULL during backfill window)
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_marginalia_uuid "
            "ON marginalia (uuid) WHERE uuid IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_reading_sessions_uuid "
            "ON reading_sessions (uuid) WHERE uuid IS NOT NULL"
        ))

    record_migration(engine, version=10, migration_name=name)
    return True


def _backfill_uuids(conn, uuid_mod) -> None:
    """Populate NULL uuid columns with uuid4().hex values."""
    for table in ("marginalia", "reading_sessions"):
        rows = list(conn.execute(text(
            f"SELECT id FROM {table} WHERE uuid IS NULL"
        )))
        for (rid,) in rows:
            conn.execute(
                text(f"UPDATE {table} SET uuid = :u WHERE id = :i"),
                {"u": uuid_mod.uuid4().hex, "i": rid},
            )
```

Update `MIGRATIONS`:

```python
MIGRATIONS = [
    # ... existing ...
    (9, "add_archived_at", migrate_add_archived_at),
    (10, "add_uri_columns", migrate_add_uri_columns),
]
```

Update `CURRENT_SCHEMA_VERSION = 10`.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_migration_10_uri_columns.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -q
```
Expected: existing tests still pass. New columns are nullable; no ORM-level impact yet (model updates come in Task 5).

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/db/migrations.py tests/test_migration_10_uri_columns.py
git commit -m "$(cat <<'EOF'
feat(db): migration 10 - add uuid, color, anchors, progress_anchor

- marginalia: uuid (UNIQUE backfilled with uuid4().hex), color
- reading_sessions: uuid (UNIQUE backfilled), start_anchor, end_anchor
- personal_metadata: progress_anchor

All new columns nullable. UUIDs enable URI addressability:
book-memex://marginalia/<uuid>, book-memex://reading/<uuid>.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Update ORM models to match new schema

**Files:**
- Modify: `book_memex/db/models.py`
- Create: `tests/test_model_new_columns.py`

With the migrations in place, update SQLAlchemy ORM classes so that new columns are visible to the Library API and service layer. Also add a `uri` hybrid property on Book, Marginalia, and ReadingSession.

- [ ] **Step 1: Write the failing test**

Create `tests/test_model_new_columns.py`:

```python
"""Test ORM visibility of new columns and URI properties."""
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import pytest

from book_memex.library_db import Library
from book_memex.db.models import Book, Marginalia, ReadingSession, PersonalMetadata
from book_memex.core.uri import parse_uri


@pytest.fixture
def temp_library():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def _add_sample_book(lib):
    p = lib.library_path / "sample.txt"
    p.write_text("hello")
    return lib.add_book(
        p,
        metadata={"title": "Sample", "creators": ["Author"]},
        extract_text=False,
    )


def test_marginalia_round_trips_new_columns(temp_library):
    book = _add_sample_book(temp_library)
    m = Marginalia(
        content="note",
        highlighted_text="passage",
        color="#ffff00",
        position={"cfi": "epubcfi(...)"},
    )
    m.books.append(book)
    temp_library.session.add(m)
    temp_library.session.commit()

    fetched = temp_library.session.get(Marginalia, m.id)
    assert fetched.uuid is not None
    assert len(fetched.uuid) == 32  # uuid4().hex
    assert fetched.color == "#ffff00"
    assert fetched.archived_at is None
    assert fetched.position == {"cfi": "epubcfi(...)"}


def test_marginalia_uri_property(temp_library):
    m = Marginalia(content="x")
    temp_library.session.add(m)
    temp_library.session.commit()
    parsed = parse_uri(m.uri)
    assert parsed.kind == "marginalia"
    assert parsed.id == m.uuid


def test_reading_session_new_columns(temp_library):
    book = _add_sample_book(temp_library)
    rs = ReadingSession(
        book_id=book.id,
        start_time=datetime.utcnow(),
        start_anchor={"cfi": "epubcfi(/6/4!/4)"},
    )
    temp_library.session.add(rs)
    temp_library.session.commit()

    fetched = temp_library.session.get(ReadingSession, rs.id)
    assert fetched.uuid is not None
    assert fetched.start_anchor == {"cfi": "epubcfi(/6/4!/4)"}
    assert fetched.end_anchor is None
    assert fetched.archived_at is None


def test_reading_session_uri_property(temp_library):
    book = _add_sample_book(temp_library)
    rs = ReadingSession(book_id=book.id, start_time=datetime.utcnow())
    temp_library.session.add(rs)
    temp_library.session.commit()
    parsed = parse_uri(rs.uri)
    assert parsed.kind == "reading"
    assert parsed.id == rs.uuid


def test_book_uri_property(temp_library):
    book = _add_sample_book(temp_library)
    parsed = parse_uri(book.uri)
    assert parsed.kind == "book"
    assert parsed.id == book.unique_id


def test_personal_metadata_progress_anchor(temp_library):
    book = _add_sample_book(temp_library)
    pm = temp_library.session.query(PersonalMetadata).filter_by(book_id=book.id).first()
    if pm is None:
        pm = PersonalMetadata(book_id=book.id)
        temp_library.session.add(pm)
    pm.progress_anchor = {"cfi": "epubcfi(/6/4!/6)", "percentage": 45}
    temp_library.session.commit()

    fetched = temp_library.session.get(PersonalMetadata, pm.id)
    assert fetched.progress_anchor == {"cfi": "epubcfi(/6/4!/6)", "percentage": 45}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_model_new_columns.py -q
```
Expected: failures like `AttributeError: Marginalia has no attribute 'uuid'` (ORM classes do not expose the new columns yet).

- [ ] **Step 3: Update ORM models**

Open `book_memex/db/models.py`. Add the new columns and URI hybrid properties.

Add at the top of the file, below the existing imports:

```python
import uuid as _uuid
from book_memex.core import uri as _uri
```

In the `Book` class, add a hybrid property (`id` and `unique_id` already exist):

```python
    @hybrid_property
    def uri(self) -> str:
        return _uri.build_book_uri(self.unique_id)
```

In the `Marginalia` class, add the new columns and URI property. Find the existing `__tablename__ = 'marginalia'` block, and update:

```python
class Marginalia(Base):
    """... existing docstring ..."""
    __tablename__ = 'marginalia'

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False,
                  default=lambda: _uuid.uuid4().hex)

    content = Column(Text)
    highlighted_text = Column(Text)

    page_number = Column(Integer)
    position = Column(JSON)

    category = Column(String(100), index=True)
    color = Column(String(7))
    pinned = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    archived_at = Column(DateTime, nullable=True)

    books = relationship('Book', secondary=marginalia_books,
                         back_populates='marginalia', lazy='selectin')

    __table_args__ = (
        Index('idx_marginalia_pinned', 'pinned'),
        Index('idx_marginalia_category', 'category'),
        Index('idx_marginalia_created', 'created_at'),
        Index('idx_marginalia_archived', 'archived_at'),
    )

    @hybrid_property
    def uri(self) -> str:
        return _uri.build_marginalia_uri(self.uuid)

    @property
    def scope(self) -> str:
        """Derive marginalia scope from the row's state."""
        n = len(self.books) if self.books is not None else 0
        has_location = self.page_number is not None or self.position is not None
        if n == 0:
            return "collection_note"
        if n == 1:
            return "highlight" if has_location else "book_note"
        return "cross_book_note"
```

In the `ReadingSession` class, add:

```python
class ReadingSession(Base):
    """... existing docstring ..."""
    __tablename__ = 'reading_sessions'

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False,
                  default=lambda: _uuid.uuid4().hex)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    start_time = Column(DateTime, default=utc_now, nullable=False)
    end_time = Column(DateTime)
    start_anchor = Column(JSON, nullable=True)
    end_anchor = Column(JSON, nullable=True)

    pages_read = Column(Integer, default=0)
    comprehension_score = Column(Float)

    archived_at = Column(DateTime, nullable=True)

    book = relationship('Book', back_populates='sessions')

    @hybrid_property
    def duration_minutes(self) -> Optional[float]:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None

    @hybrid_property
    def uri(self) -> str:
        return _uri.build_reading_uri(self.uuid)
```

In `PersonalMetadata`, add the new column near the existing fields:

```python
    progress_anchor = Column(JSON, nullable=True)
    archived_at = Column(DateTime, nullable=True)
```

Also add `archived_at` columns to: `Book`, `Author`, `Subject`, `Tag`, `File`, `Cover`. Each becomes:

```python
    archived_at = Column(DateTime, nullable=True)
```

placed near the existing timestamp fields.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_model_new_columns.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -q
```
Expected: all existing tests still pass. If any existing test asserts on an exhaustive column list or an ORM introspection that changes with the new columns, update the assertion.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/db/models.py tests/test_model_new_columns.py
git commit -m "$(cat <<'EOF'
feat(db): expose uuid/color/anchors/archived_at in ORM models

- Marginalia: uuid (default uuid4().hex), color, archived_at, scope
  property, uri hybrid property
- ReadingSession: uuid, start_anchor, end_anchor, archived_at, uri
- PersonalMetadata: progress_anchor, archived_at
- Book: uri hybrid property
- archived_at added to Book, Author, Subject, Tag, File, Cover

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Soft-delete helper module

**Files:**
- Create: `book_memex/core/soft_delete.py`
- Create: `tests/test_soft_delete.py`

A small helper module with two operations: `filter_active(query, model)` to filter out archived rows, and `archive(instance)` / `restore(instance)` / `hard_delete(session, instance)` helpers. Used by services and MCP tools.

- [ ] **Step 1: Write the failing test**

Create `tests/test_soft_delete.py`:

```python
"""Unit tests for soft-delete helpers."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import Marginalia
from book_memex.core.soft_delete import (
    filter_active, archive, restore, hard_delete, is_archived,
)


@pytest.fixture
def lib():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_filter_active_excludes_archived(lib):
    m1 = Marginalia(content="kept")
    m2 = Marginalia(content="archived")
    lib.session.add_all([m1, m2])
    lib.session.commit()
    archive(lib.session, m2)
    lib.session.commit()

    active = filter_active(lib.session.query(Marginalia), Marginalia).all()
    ids = {m.id for m in active}
    assert m1.id in ids
    assert m2.id not in ids


def test_archive_sets_timestamp(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    assert m.archived_at is None
    archive(lib.session, m)
    lib.session.commit()
    assert m.archived_at is not None
    assert is_archived(m)


def test_restore_clears_timestamp(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    archive(lib.session, m); lib.session.commit()
    restore(lib.session, m); lib.session.commit()
    assert m.archived_at is None
    assert not is_archived(m)


def test_hard_delete_removes_row(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    mid = m.id
    hard_delete(lib.session, m); lib.session.commit()
    assert lib.session.get(Marginalia, mid) is None


def test_filter_active_respects_include_archived(lib):
    m1 = Marginalia(content="a"); m2 = Marginalia(content="b")
    lib.session.add_all([m1, m2]); lib.session.commit()
    archive(lib.session, m2); lib.session.commit()

    all_rows = filter_active(
        lib.session.query(Marginalia), Marginalia, include_archived=True
    ).all()
    assert len(all_rows) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_soft_delete.py -q
```
Expected: `ImportError: cannot import name 'filter_active' from 'book_memex.core.soft_delete'`.

- [ ] **Step 3: Implement the helper**

Create `book_memex/core/soft_delete.py`:

```python
"""Soft-delete helpers for memex-family records.

Every table with an `archived_at TIMESTAMP NULL` column participates.
Convention: archived rows are filtered out of default queries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Type

from sqlalchemy.orm import Query, Session


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def filter_active(query: Query, model: Type, *, include_archived: bool = False) -> Query:
    """Filter a query to exclude archived rows unless `include_archived` is True."""
    if include_archived:
        return query
    return query.filter(model.archived_at.is_(None))


def archive(session: Session, instance) -> None:
    """Mark a single row as archived. Caller must commit."""
    instance.archived_at = _utc_now()
    session.add(instance)


def restore(session: Session, instance) -> None:
    """Clear archived_at on a row. Caller must commit."""
    instance.archived_at = None
    session.add(instance)


def hard_delete(session: Session, instance) -> None:
    """Delete a row physically. Caller must commit."""
    session.delete(instance)


def is_archived(instance) -> bool:
    """Whether a row is currently archived."""
    return getattr(instance, "archived_at", None) is not None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_soft_delete.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:
```bash
git add book_memex/core/soft_delete.py tests/test_soft_delete.py
git commit -m "$(cat <<'EOF'
feat(core): add soft-delete helpers

filter_active() for queries, archive()/restore()/hard_delete() for
individual rows, is_archived() predicate. Used by services + MCP
tools to implement the workspace soft-delete convention.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Extend MarginaliaService with soft-delete and URI-aware operations

**Files:**
- Modify: `book_memex/services/marginalia_service.py`
- Create: `tests/test_marginalia_service_extended.py`

Extend the existing `MarginaliaService` with: `include_archived` flag on list methods, a `scope` filter, a `get_by_uuid` method, `archive`/`restore`/`hard_delete` methods, and a `create` that accepts a `color` field.

- [ ] **Step 1: Write the failing test**

Create `tests/test_marginalia_service_extended.py`:

```python
"""Tests for MarginaliaService's extended API (soft-delete, scope filter, uuid)."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.services.marginalia_service import MarginaliaService


@pytest.fixture
def lib_with_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"
    p.write_text("hello")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_with_color(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(
        content="note",
        highlighted_text="passage",
        book_ids=[book.id],
        page_number=5,
        color="#ff0000",
    )
    assert m.color == "#ff0000"
    assert m.uuid is not None


def test_scope_derivation(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    # Collection note (0 books)
    m0 = svc.create(content="c")
    assert m0.scope == "collection_note"
    # Book note (1 book, no location)
    m1 = svc.create(content="bn", book_ids=[book.id])
    assert m1.scope == "book_note"
    # Highlight (1 book + location)
    m2 = svc.create(content="h", book_ids=[book.id], page_number=3)
    assert m2.scope == "highlight"


def test_list_for_book_filters_archived_by_default(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m1 = svc.create(content="a", book_ids=[book.id])
    m2 = svc.create(content="b", book_ids=[book.id])
    svc.archive(m2)

    active = svc.list_for_book(book.id)
    assert m1.id in {m.id for m in active}
    assert m2.id not in {m.id for m in active}

    with_archived = svc.list_for_book(book.id, include_archived=True)
    assert {m1.id, m2.id}.issubset({m.id for m in with_archived})


def test_list_for_book_with_scope_filter(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    bn = svc.create(content="bn", book_ids=[book.id])
    hl = svc.create(content="h", book_ids=[book.id], page_number=1)

    highlights = svc.list_for_book(book.id, scope="highlight")
    assert hl.id in {m.id for m in highlights}
    assert bn.id not in {m.id for m in highlights}


def test_get_by_uuid(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(content="x", book_ids=[book.id])
    fetched = svc.get_by_uuid(m.uuid)
    assert fetched is not None
    assert fetched.id == m.id


def test_archive_restore_cycle(lib_with_book):
    lib, book = lib_with_book
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(content="x", book_ids=[book.id])
    svc.archive(m)
    assert m.archived_at is not None
    svc.restore(m)
    assert m.archived_at is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_marginalia_service_extended.py -q
```
Expected: failures on missing methods (`archive`, `restore`, `get_by_uuid`, `scope` filter, `color` parameter).

- [ ] **Step 3: Extend MarginaliaService**

Open `book_memex/services/marginalia_service.py`. Add imports:

```python
from book_memex.core.soft_delete import (
    filter_active, archive as _archive, restore as _restore,
    hard_delete as _hard_delete,
)
```

Update `create` to accept `color`:

```python
    def create(
        self,
        content: Optional[str] = None,
        highlighted_text: Optional[str] = None,
        book_ids: Optional[List[int]] = None,
        page_number: Optional[int] = None,
        position: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        color: Optional[str] = None,
        pinned: bool = False,
    ) -> Marginalia:
        """Create a new marginalia entry."""
        if not content and not highlighted_text:
            raise ValueError("At least one of content or highlighted_text is required")

        entry = Marginalia(
            content=content,
            highlighted_text=highlighted_text,
            page_number=page_number,
            position=position,
            category=category,
            color=color,
            pinned=pinned,
        )
        self.session.add(entry)
        self.session.flush()

        if book_ids:
            for book_id in book_ids:
                book = self.session.get(Book, book_id)
                if book:
                    entry.books.append(book)

        self.session.commit()
        return entry
```

Add a new method `get_by_uuid`:

```python
    def get_by_uuid(self, uuid: str) -> Optional[Marginalia]:
        """Fetch a marginalia row by its uuid. Returns None if not found."""
        return (
            self.session.query(Marginalia)
            .filter_by(uuid=uuid)
            .first()
        )
```

Replace or extend the existing `list_for_book` so it supports `scope` and `include_archived`:

```python
    def list_for_book(
        self,
        book_id: int,
        scope: Optional[str] = None,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> List[Marginalia]:
        """List marginalia associated with a book.

        scope: optional filter ("highlight", "book_note", "collection_note",
               "cross_book_note"). Applied in Python after the DB filter.
        """
        q = (
            self.session.query(Marginalia)
            .join(Marginalia.books)
            .filter(Book.id == book_id)
        )
        q = filter_active(q, Marginalia, include_archived=include_archived)
        q = q.order_by(Marginalia.created_at.desc())
        if limit:
            q = q.limit(limit)
        rows = q.all()
        if scope:
            rows = [r for r in rows if r.scope == scope]
        return rows
```

Add soft-delete methods:

```python
    def archive(self, entry: Marginalia) -> None:
        _archive(self.session, entry)
        self.session.commit()

    def restore(self, entry: Marginalia) -> None:
        _restore(self.session, entry)
        self.session.commit()

    def hard_delete(self, entry: Marginalia) -> None:
        _hard_delete(self.session, entry)
        self.session.commit()
```

Keep the existing `get(marginalia_id)` method (by Integer id) intact for callers that hold an id.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_marginalia_service_extended.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -q
```
Expected: all existing tests still pass. If an existing test asserts on the `create` signature, update it.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/services/marginalia_service.py tests/test_marginalia_service_extended.py
git commit -m "$(cat <<'EOF'
feat(services): extend MarginaliaService with soft-delete + scope + uuid

- create() accepts `color` (hex string for highlights)
- list_for_book() accepts `scope` filter and `include_archived` flag
- get_by_uuid() for URI-keyed lookup
- archive()/restore()/hard_delete() wrapping soft-delete helpers

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Marginalia REST endpoints

**Files:**
- Modify: `book_memex/server.py` (add a router for marginalia)
- Create: `tests/test_server_marginalia.py`

Add the endpoints from spec §6.2. Use FastAPI's existing patterns in `server.py` (check nearby routes for Pydantic model conventions, error shapes, etc. before writing). If `server.py` does not yet have a clear routing structure, add a new router module at `book_memex/server/routes/marginalia.py` and mount it.

For this task assume the router is added directly in `server.py` following that file's existing style.

- [ ] **Step 1: Inspect existing server.py routing style**

Read `book_memex/server.py` lines 1-200 and grep for `@app.get`, `@app.post`, and any `APIRouter` usage. Determine:
1. Is routing organized as `@app.<method>(...)` on the FastAPI app directly, or via `APIRouter()`?
2. How do existing endpoints read the library / database? (Likely a dependency `get_library()`.)
3. How are errors returned? (`HTTPException`? `JSONResponse`?)

Make the new endpoints match the existing style exactly. The tests below assume a `FastAPI` app instance exported as `app` at module level, reachable via `TestClient`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_server_marginalia.py`:

```python
"""Integration tests for /api/marginalia endpoints."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library  # set_library is an override for tests


@pytest.fixture
def client_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("hello")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_marginalia(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/marginalia", json={
        "book_ids": [book.id],
        "content": "note",
        "highlighted_text": "passage",
        "color": "#ffff00",
        "page_number": 3,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["uri"].startswith("book-memex://marginalia/")
    assert data["color"] == "#ffff00"
    assert data["uuid"]


def test_list_marginalia_for_book(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "a"})
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "b"})
    r = client.get(f"/api/marginalia?book_id={book.id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2


def test_get_marginalia_by_uuid(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    r = client.get(f"/api/marginalia/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["uuid"] == created["uuid"]


def test_patch_marginalia(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    r = client.patch(f"/api/marginalia/{created['uuid']}", json={"content": "y", "color": "#ff0000"})
    assert r.status_code == 200
    assert r.json()["content"] == "y"
    assert r.json()["color"] == "#ff0000"


def test_soft_delete_and_restore(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    uuid = created["uuid"]

    # Default delete is soft.
    r = client.delete(f"/api/marginalia/{uuid}")
    assert r.status_code == 204

    # Default list filters archived.
    items = client.get(f"/api/marginalia?book_id={book.id}").json()
    assert uuid not in {m["uuid"] for m in items}

    # include_archived exposes it.
    items = client.get(f"/api/marginalia?book_id={book.id}&include_archived=true").json()
    assert uuid in {m["uuid"] for m in items}

    # Restore clears archived_at.
    r = client.post(f"/api/marginalia/{uuid}/restore")
    assert r.status_code == 200
    items = client.get(f"/api/marginalia?book_id={book.id}").json()
    assert uuid in {m["uuid"] for m in items}


def test_hard_delete(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    uuid = created["uuid"]

    r = client.delete(f"/api/marginalia/{uuid}?hard=true")
    assert r.status_code == 204

    r = client.get(f"/api/marginalia/{uuid}")
    assert r.status_code == 404


def test_scope_filter(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "bn"})
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "h", "page_number": 5})
    items = client.get(f"/api/marginalia?book_id={book.id}&scope=highlight").json()
    assert all(m["scope"] == "highlight" for m in items)
    assert len(items) == 1
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
pytest tests/test_server_marginalia.py -q
```
Expected: `ImportError: cannot import name 'set_library' from 'book_memex.server'` or 404s because the endpoints do not exist.

- [ ] **Step 4: Implement the endpoints**

Open `book_memex/server.py`. At the top, add imports:

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Query
from book_memex.services.marginalia_service import MarginaliaService
```

Add Pydantic request/response models (near other Pydantic models in the file, or at the bottom of a "routes/schemas" section):

```python
class MarginaliaCreate(BaseModel):
    book_ids: List[int] = Field(default_factory=list)
    content: Optional[str] = None
    highlighted_text: Optional[str] = None
    page_number: Optional[int] = None
    position: Optional[dict] = None
    category: Optional[str] = None
    color: Optional[str] = None
    pinned: bool = False


class MarginaliaUpdate(BaseModel):
    content: Optional[str] = None
    highlighted_text: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    pinned: Optional[bool] = None


class MarginaliaOut(BaseModel):
    uuid: str
    uri: str
    content: Optional[str]
    highlighted_text: Optional[str]
    page_number: Optional[int]
    position: Optional[dict]
    category: Optional[str]
    color: Optional[str]
    pinned: bool
    scope: str
    archived_at: Optional[str]
    created_at: str
    updated_at: str
    book_ids: List[int]

    @classmethod
    def from_orm(cls, m) -> "MarginaliaOut":
        return cls(
            uuid=m.uuid,
            uri=m.uri,
            content=m.content,
            highlighted_text=m.highlighted_text,
            page_number=m.page_number,
            position=m.position,
            category=m.category,
            color=m.color,
            pinned=bool(m.pinned),
            scope=m.scope,
            archived_at=m.archived_at.isoformat() if m.archived_at else None,
            created_at=m.created_at.isoformat(),
            updated_at=m.updated_at.isoformat() if m.updated_at else m.created_at.isoformat(),
            book_ids=[b.id for b in m.books],
        )
```

If `server.py` already has a `get_library()` dependency, reuse it. If not, add this pattern (or equivalent; match existing style):

```python
_LIBRARY = None

def set_library(lib):
    """Testing hook: override the library used by the API."""
    global _LIBRARY
    _LIBRARY = lib

def get_library():
    if _LIBRARY is None:
        raise RuntimeError("Library not initialized. Call set_library() first.")
    return _LIBRARY
```

Then add the endpoints:

```python
@app.post("/api/marginalia", response_model=MarginaliaOut, status_code=201)
def create_marginalia(payload: MarginaliaCreate):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.create(
        content=payload.content,
        highlighted_text=payload.highlighted_text,
        book_ids=payload.book_ids,
        page_number=payload.page_number,
        position=payload.position,
        category=payload.category,
        color=payload.color,
        pinned=payload.pinned,
    )
    return MarginaliaOut.from_orm(m)


@app.get("/api/marginalia", response_model=List[MarginaliaOut])
def list_marginalia(
    book_id: Optional[int] = None,
    scope: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 100,
):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    if book_id is None:
        raise HTTPException(400, "book_id is required for now (cross-book listing not yet supported)")
    rows = svc.list_for_book(book_id, scope=scope, include_archived=include_archived, limit=limit)
    return [MarginaliaOut.from_orm(m) for m in rows]


@app.get("/api/marginalia/{uuid}", response_model=MarginaliaOut)
def get_marginalia(uuid: str):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise HTTPException(404, f"Marginalia {uuid} not found")
    return MarginaliaOut.from_orm(m)


@app.patch("/api/marginalia/{uuid}", response_model=MarginaliaOut)
def update_marginalia(uuid: str, payload: MarginaliaUpdate):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise HTTPException(404, f"Marginalia {uuid} not found")
    if payload.content is not None:
        m.content = payload.content
    if payload.highlighted_text is not None:
        m.highlighted_text = payload.highlighted_text
    if payload.category is not None:
        m.category = payload.category
    if payload.color is not None:
        m.color = payload.color
    if payload.pinned is not None:
        m.pinned = payload.pinned
    lib.session.commit()
    return MarginaliaOut.from_orm(m)


@app.delete("/api/marginalia/{uuid}", status_code=204)
def delete_marginalia(uuid: str, hard: bool = False):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise HTTPException(404, f"Marginalia {uuid} not found")
    if hard:
        svc.hard_delete(m)
    else:
        svc.archive(m)
    return None


@app.post("/api/marginalia/{uuid}/restore", response_model=MarginaliaOut)
def restore_marginalia(uuid: str):
    lib = get_library()
    svc = MarginaliaService(lib.session, lib.library_path)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise HTTPException(404, f"Marginalia {uuid} not found")
    svc.restore(m)
    return MarginaliaOut.from_orm(m)
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_server_marginalia.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Run the full test suite**

Run:
```bash
pytest -q
```
Expected: all prior tests still pass.

- [ ] **Step 7: Commit**

Run:
```bash
git add book_memex/server.py tests/test_server_marginalia.py
git commit -m "$(cat <<'EOF'
feat(api): add /api/marginalia CRUD + restore endpoints

- POST /api/marginalia (create)
- GET /api/marginalia?book_id=... (list with scope + include_archived)
- GET /api/marginalia/{uuid} (get by uuid)
- PATCH /api/marginalia/{uuid} (update editable fields)
- DELETE /api/marginalia/{uuid}?hard={false|true}
- POST /api/marginalia/{uuid}/restore

Every response includes uri (book-memex://marginalia/<uuid>) and
derived scope (highlight, book_note, collection_note, cross_book_note).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Marginalia MCP tools

**Files:**
- Modify: `book_memex/mcp/tools.py`
- Modify: `book_memex/mcp/server.py`
- Create: `tests/test_mcp_marginalia_tools.py`

Expose marginalia CRUD over MCP. Tools accept book URIs (not Integer ids) to be consistent with the cross-archive URI convention.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_marginalia_tools.py`:

```python
"""Tests for MCP marginalia tool implementations."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    list_marginalia_impl, get_marginalia_impl, add_marginalia_impl,
    update_marginalia_impl, delete_marginalia_impl, restore_marginalia_impl,
)


@pytest.fixture
def lib_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_add_marginalia_by_uri(lib_and_book):
    lib, book = lib_and_book
    result = add_marginalia_impl(
        lib.session,
        book_uris=[book.uri],
        content="note",
        highlighted_text="passage",
        page_number=5,
        color="#ffff00",
    )
    assert result["uri"].startswith("book-memex://marginalia/")
    assert result["scope"] == "highlight"


def test_list_marginalia(lib_and_book):
    lib, book = lib_and_book
    add_marginalia_impl(lib.session, book_uris=[book.uri], content="a")
    add_marginalia_impl(lib.session, book_uris=[book.uri], content="b")
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert len(rows) == 2


def test_get_marginalia_by_uuid(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    fetched = get_marginalia_impl(lib.session, uuid=created["uuid"])
    assert fetched["uuid"] == created["uuid"]


def test_update_marginalia(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    updated = update_marginalia_impl(
        lib.session, uuid=created["uuid"], color="#ff0000"
    )
    assert updated["color"] == "#ff0000"


def test_soft_delete_and_restore(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    uuid = created["uuid"]

    delete_marginalia_impl(lib.session, uuid=uuid)
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid not in {r["uuid"] for r in rows}

    restore_marginalia_impl(lib.session, uuid=uuid)
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid in {r["uuid"] for r in rows}


def test_hard_delete(lib_and_book):
    lib, book = lib_and_book
    created = add_marginalia_impl(lib.session, book_uris=[book.uri], content="x")
    uuid = created["uuid"]
    delete_marginalia_impl(lib.session, uuid=uuid, hard=True)
    with pytest.raises(LookupError):
        get_marginalia_impl(lib.session, uuid=uuid)


def test_add_rejects_invalid_uri(lib_and_book):
    lib, _ = lib_and_book
    with pytest.raises(ValueError):
        add_marginalia_impl(lib.session, book_uris=["not-a-uri"], content="x")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_mcp_marginalia_tools.py -q
```
Expected: import errors on the `*_impl` functions.

- [ ] **Step 3: Implement the tool functions**

Add to `book_memex/mcp/tools.py` (top-level imports first):

```python
from book_memex.core.uri import parse_uri, InvalidUriError
from book_memex.db.models import Marginalia
from book_memex.services.marginalia_service import MarginaliaService
```

Add a helper:

```python
def _marginalia_to_dict(m: Marginalia) -> Dict[str, Any]:
    return {
        "uuid": m.uuid,
        "uri": m.uri,
        "content": m.content,
        "highlighted_text": m.highlighted_text,
        "page_number": m.page_number,
        "position": m.position,
        "category": m.category,
        "color": m.color,
        "pinned": bool(m.pinned),
        "scope": m.scope,
        "archived_at": m.archived_at.isoformat() if m.archived_at else None,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat() if m.updated_at else m.created_at.isoformat(),
        "book_ids": [b.id for b in m.books],
        "book_uris": [b.uri for b in m.books],
    }


def _resolve_book_uris(session: Session, book_uris: List[str]) -> List[int]:
    """Parse a list of book URIs and return their Integer IDs."""
    ids = []
    for u in book_uris:
        try:
            parsed = parse_uri(u)
        except InvalidUriError as e:
            raise ValueError(f"invalid URI {u!r}: {e}") from e
        if parsed.kind != "book":
            raise ValueError(f"expected a book URI, got {parsed.kind!r}: {u}")
        book = session.query(Book).filter_by(unique_id=parsed.id).first()
        if book is None:
            raise LookupError(f"Book not found: {u}")
        ids.append(book.id)
    return ids
```

Add the tool impls:

```python
def add_marginalia_impl(
    session: Session,
    *,
    book_uris: List[str],
    content: Optional[str] = None,
    highlighted_text: Optional[str] = None,
    page_number: Optional[int] = None,
    position: Optional[Dict[str, Any]] = None,
    category: Optional[str] = None,
    color: Optional[str] = None,
    pinned: bool = False,
) -> Dict[str, Any]:
    """Create marginalia linked to 0+ books by URI."""
    book_ids = _resolve_book_uris(session, book_uris) if book_uris else []
    svc = MarginaliaService(session)
    m = svc.create(
        content=content,
        highlighted_text=highlighted_text,
        book_ids=book_ids,
        page_number=page_number,
        position=position,
        category=category,
        color=color,
        pinned=pinned,
    )
    return _marginalia_to_dict(m)


def list_marginalia_impl(
    session: Session,
    *,
    book_id: Optional[int] = None,
    scope: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    svc = MarginaliaService(session)
    if book_id is None:
        raise ValueError("book_id is required for now")
    rows = svc.list_for_book(
        book_id, scope=scope, include_archived=include_archived, limit=limit
    )
    return [_marginalia_to_dict(m) for m in rows]


def get_marginalia_impl(session: Session, *, uuid: str) -> Dict[str, Any]:
    svc = MarginaliaService(session)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise LookupError(f"Marginalia {uuid} not found")
    return _marginalia_to_dict(m)


def update_marginalia_impl(
    session: Session,
    *,
    uuid: str,
    content: Optional[str] = None,
    highlighted_text: Optional[str] = None,
    category: Optional[str] = None,
    color: Optional[str] = None,
    pinned: Optional[bool] = None,
) -> Dict[str, Any]:
    svc = MarginaliaService(session)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise LookupError(f"Marginalia {uuid} not found")
    if content is not None: m.content = content
    if highlighted_text is not None: m.highlighted_text = highlighted_text
    if category is not None: m.category = category
    if color is not None: m.color = color
    if pinned is not None: m.pinned = pinned
    session.commit()
    return _marginalia_to_dict(m)


def delete_marginalia_impl(session: Session, *, uuid: str, hard: bool = False) -> Dict[str, Any]:
    svc = MarginaliaService(session)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise LookupError(f"Marginalia {uuid} not found")
    if hard:
        svc.hard_delete(m)
    else:
        svc.archive(m)
    return {"status": "ok", "uuid": uuid, "hard": hard}


def restore_marginalia_impl(session: Session, *, uuid: str) -> Dict[str, Any]:
    svc = MarginaliaService(session)
    m = svc.get_by_uuid(uuid)
    if m is None:
        raise LookupError(f"Marginalia {uuid} not found")
    svc.restore(m)
    return _marginalia_to_dict(m)
```

- [ ] **Step 4: Register the tools in the MCP server**

Open `book_memex/mcp/server.py`. In `create_mcp_server`, after the existing `get_schema`/`execute_sql`/`update_books` tools, add:

```python
    from book_memex.mcp.tools import (
        list_marginalia_impl, get_marginalia_impl, add_marginalia_impl,
        update_marginalia_impl, delete_marginalia_impl, restore_marginalia_impl,
    )

    @mcp.tool(
        name="list_marginalia",
        description="List marginalia for a book. Optional scope filter: "
        "highlight, book_note, collection_note, cross_book_note.",
    )
    def list_marginalia(
        book_id: int, scope: str | None = None,
        include_archived: bool = False, limit: int = 50,
    ) -> list:
        return list_marginalia_impl(
            library.session, book_id=book_id, scope=scope,
            include_archived=include_archived, limit=limit,
        )

    @mcp.tool(
        name="get_marginalia",
        description="Get a marginalia record by uuid (or by URI - both accepted).",
    )
    def get_marginalia(uuid: str) -> dict:
        return get_marginalia_impl(library.session, uuid=uuid)

    @mcp.tool(
        name="add_marginalia",
        description="Create marginalia linked to 0 or more books by URI. "
        "A single book + location = highlight; single book no location = book_note; "
        "no books = collection_note; multiple books = cross_book_note.",
    )
    def add_marginalia(
        book_uris: list[str],
        content: str | None = None,
        highlighted_text: str | None = None,
        page_number: int | None = None,
        position: dict | None = None,
        category: str | None = None,
        color: str | None = None,
        pinned: bool = False,
    ) -> dict:
        return add_marginalia_impl(
            library.session, book_uris=book_uris, content=content,
            highlighted_text=highlighted_text, page_number=page_number,
            position=position, category=category, color=color, pinned=pinned,
        )

    @mcp.tool(
        name="update_marginalia",
        description="Update editable fields of a marginalia by uuid.",
    )
    def update_marginalia(
        uuid: str,
        content: str | None = None,
        highlighted_text: str | None = None,
        category: str | None = None,
        color: str | None = None,
        pinned: bool | None = None,
    ) -> dict:
        return update_marginalia_impl(
            library.session, uuid=uuid, content=content,
            highlighted_text=highlighted_text, category=category,
            color=color, pinned=pinned,
        )

    @mcp.tool(
        name="delete_marginalia",
        description="Soft-delete a marginalia (archive it). Pass hard=True to irreversibly delete.",
    )
    def delete_marginalia(uuid: str, hard: bool = False) -> dict:
        return delete_marginalia_impl(library.session, uuid=uuid, hard=hard)

    @mcp.tool(
        name="restore_marginalia",
        description="Restore a soft-deleted marginalia (clear archived_at).",
    )
    def restore_marginalia(uuid: str) -> dict:
        return restore_marginalia_impl(library.session, uuid=uuid)
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_mcp_marginalia_tools.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/mcp/tools.py book_memex/mcp/server.py tests/test_mcp_marginalia_tools.py
git commit -m "$(cat <<'EOF'
feat(mcp): add marginalia CRUD + restore tools

Six new tools: list_marginalia, get_marginalia, add_marginalia,
update_marginalia, delete_marginalia (hard flag), restore_marginalia.

add_marginalia accepts book URIs (book-memex://book/<unique_id>)
matching the cross-archive URI convention. Scope is returned in
every response, derived from book linkage + location data.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: ReadingSession service

**Files:**
- Create: `book_memex/services/reading_session_service.py`
- Create: `tests/test_reading_session_service.py`

A new service layer around ReadingSession. Operations: `start`, `end`, `get_by_uuid`, `list_for_book`, `archive`, `restore`, `hard_delete`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_reading_session_service.py`:

```python
"""Tests for ReadingSessionService."""
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from book_memex.library_db import Library
from book_memex.services.reading_session_service import ReadingSessionService


@pytest.fixture
def lib_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_start_session(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id, start_anchor={"cfi": "epubcfi(/6/4!/4)"})
    assert rs.uuid is not None
    assert rs.start_anchor == {"cfi": "epubcfi(/6/4!/4)"}
    assert rs.end_time is None


def test_end_session(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    ended = svc.end(rs.uuid, end_anchor={"cfi": "epubcfi(/6/4!/8)"})
    assert ended.end_time is not None
    assert ended.end_anchor == {"cfi": "epubcfi(/6/4!/8)"}


def test_end_idempotent_on_already_ended(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    svc.end(rs.uuid)
    # Ending again should either return the already-ended session
    # or raise a clear error. Spec: idempotent.
    again = svc.end(rs.uuid)
    assert again.uuid == rs.uuid


def test_list_for_book_filters_archived(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs1 = svc.start(book_id=book.id)
    rs2 = svc.start(book_id=book.id)
    svc.archive(rs2)

    active = svc.list_for_book(book.id)
    assert rs1.uuid in {r.uuid for r in active}
    assert rs2.uuid not in {r.uuid for r in active}


def test_archive_restore(lib_and_book):
    lib, book = lib_and_book
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=book.id)
    svc.archive(rs)
    assert rs.archived_at is not None
    svc.restore(rs)
    assert rs.archived_at is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_reading_session_service.py -q
```
Expected: `ImportError: No module named 'book_memex.services.reading_session_service'`.

- [ ] **Step 3: Implement the service**

Create `book_memex/services/reading_session_service.py`:

```python
"""Service layer for ReadingSession records."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from book_memex.db.models import ReadingSession, Book
from book_memex.core.soft_delete import (
    filter_active, archive as _archive,
    restore as _restore, hard_delete as _hard_delete,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReadingSessionService:
    def __init__(self, session: Session, library_path=None):
        self.session = session
        self.library_path = library_path

    def start(
        self,
        book_id: int,
        start_anchor: Optional[Dict[str, Any]] = None,
    ) -> ReadingSession:
        book = self.session.get(Book, book_id)
        if book is None:
            raise LookupError(f"Book {book_id} not found")
        rs = ReadingSession(
            book_id=book_id,
            start_time=_utc_now(),
            start_anchor=start_anchor,
        )
        self.session.add(rs)
        self.session.commit()
        return rs

    def end(
        self,
        uuid: str,
        end_anchor: Optional[Dict[str, Any]] = None,
    ) -> ReadingSession:
        rs = self.get_by_uuid(uuid)
        if rs is None:
            raise LookupError(f"ReadingSession {uuid} not found")
        if rs.end_time is None:
            rs.end_time = _utc_now()
        if end_anchor is not None:
            rs.end_anchor = end_anchor
        self.session.commit()
        return rs

    def get_by_uuid(self, uuid: str) -> Optional[ReadingSession]:
        return (
            self.session.query(ReadingSession)
            .filter_by(uuid=uuid)
            .first()
        )

    def list_for_book(
        self,
        book_id: int,
        include_archived: bool = False,
        limit: Optional[int] = None,
    ) -> List[ReadingSession]:
        q = self.session.query(ReadingSession).filter_by(book_id=book_id)
        q = filter_active(q, ReadingSession, include_archived=include_archived)
        q = q.order_by(ReadingSession.start_time.desc())
        if limit:
            q = q.limit(limit)
        return q.all()

    def archive(self, rs: ReadingSession) -> None:
        _archive(self.session, rs)
        self.session.commit()

    def restore(self, rs: ReadingSession) -> None:
        _restore(self.session, rs)
        self.session.commit()

    def hard_delete(self, rs: ReadingSession) -> None:
        _hard_delete(self.session, rs)
        self.session.commit()
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_reading_session_service.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:
```bash
git add book_memex/services/reading_session_service.py tests/test_reading_session_service.py
git commit -m "$(cat <<'EOF'
feat(services): add ReadingSessionService

start(), end() (idempotent), get_by_uuid(), list_for_book() with
include_archived flag, and archive/restore/hard_delete wrapping
the soft-delete helpers. end() auto-timestamps end_time and stores
the optional end_anchor JSON.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Reading state REST endpoints

**Files:**
- Modify: `book_memex/server.py`
- Create: `tests/test_server_reading.py`

Two endpoint groups: reading sessions (start, end, list, delete, restore) and reading progress (get, post, patch). Progress writes to `PersonalMetadata.progress_anchor` and optionally updates the `reading_progress` scalar. `POST /api/reading/progress` accepts only if new anchor is at or after current (per spec §6.3); `PATCH` always wins.

- [ ] **Step 1: Write the failing test**

Create `tests/test_server_reading.py`:

```python
"""Integration tests for /api/reading/* endpoints."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library


@pytest.fixture
def client_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


# --- Reading sessions ---

def test_start_and_end_session(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/reading/sessions/start", json={
        "book_id": book.id,
        "start_anchor": {"cfi": "epubcfi(/6/4!/4)"},
    })
    assert r.status_code == 201
    data = r.json()
    assert data["uri"].startswith("book-memex://reading/")
    uuid = data["uuid"]

    r = client.post(f"/api/reading/sessions/{uuid}/end", json={
        "end_anchor": {"cfi": "epubcfi(/6/4!/8)"},
    })
    assert r.status_code == 200
    assert r.json()["end_time"] is not None


def test_list_sessions(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/reading/sessions/start", json={"book_id": book.id})
    client.post("/api/reading/sessions/start", json={"book_id": book.id})
    r = client.get(f"/api/reading/sessions?book_id={book.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_delete_and_restore_session(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/reading/sessions/start", json={"book_id": book.id}).json()
    uuid = created["uuid"]

    r = client.delete(f"/api/reading/sessions/{uuid}")
    assert r.status_code == 204
    listed = client.get(f"/api/reading/sessions?book_id={book.id}").json()
    assert uuid not in {s["uuid"] for s in listed}

    client.post(f"/api/reading/sessions/{uuid}/restore")
    listed = client.get(f"/api/reading/sessions?book_id={book.id}").json()
    assert uuid in {s["uuid"] for s in listed}


# --- Reading progress ---

def test_progress_post_and_get(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "epubcfi(/6/4!/4)"},
        "percentage": 10,
    })
    assert r.status_code == 200

    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["anchor"] == {"cfi": "epubcfi(/6/4!/4)"}
    assert data["percentage"] == 10


def test_progress_post_rejects_older_anchor(client_and_book):
    """POST must reject a backwards anchor (compared by percentage)."""
    client, book, _ = client_and_book
    client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "X"},
        "percentage": 50,
    })
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "Y"},
        "percentage": 20,
    })
    # Rejected with 409 Conflict or 400. Either is acceptable; spec says reject.
    assert r.status_code in (400, 409)

    # Current progress is still the forward one.
    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.json()["percentage"] == 50


def test_progress_patch_always_wins(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "X"},
        "percentage": 80,
    })
    r = client.patch("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "Y"},
        "percentage": 10,
    })
    assert r.status_code == 200
    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.json()["percentage"] == 10
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_server_reading.py -q
```
Expected: 404s on the missing endpoints.

- [ ] **Step 3: Implement the endpoints**

In `book_memex/server.py`, add Pydantic models:

```python
class StartSessionIn(BaseModel):
    book_id: int
    start_anchor: Optional[dict] = None


class EndSessionIn(BaseModel):
    end_anchor: Optional[dict] = None


class ReadingSessionOut(BaseModel):
    uuid: str
    uri: str
    book_id: int
    start_time: str
    end_time: Optional[str]
    start_anchor: Optional[dict]
    end_anchor: Optional[dict]
    pages_read: Optional[int]
    archived_at: Optional[str]

    @classmethod
    def from_orm(cls, rs) -> "ReadingSessionOut":
        return cls(
            uuid=rs.uuid,
            uri=rs.uri,
            book_id=rs.book_id,
            start_time=rs.start_time.isoformat(),
            end_time=rs.end_time.isoformat() if rs.end_time else None,
            start_anchor=rs.start_anchor,
            end_anchor=rs.end_anchor,
            pages_read=rs.pages_read,
            archived_at=rs.archived_at.isoformat() if rs.archived_at else None,
        )


class ProgressIn(BaseModel):
    book_id: int
    anchor: dict
    percentage: Optional[float] = None


class ProgressOut(BaseModel):
    book_id: int
    anchor: Optional[dict]
    percentage: Optional[float]
    updated_at: Optional[str]
```

Import the service and PersonalMetadata:

```python
from book_memex.services.reading_session_service import ReadingSessionService
from book_memex.db.models import PersonalMetadata
```

Add session endpoints:

```python
@app.post("/api/reading/sessions/start", response_model=ReadingSessionOut, status_code=201)
def start_reading_session(payload: StartSessionIn):
    lib = get_library()
    svc = ReadingSessionService(lib.session)
    rs = svc.start(book_id=payload.book_id, start_anchor=payload.start_anchor)
    return ReadingSessionOut.from_orm(rs)


@app.post("/api/reading/sessions/{uuid}/end", response_model=ReadingSessionOut)
def end_reading_session(uuid: str, payload: EndSessionIn):
    lib = get_library()
    svc = ReadingSessionService(lib.session)
    try:
        rs = svc.end(uuid, end_anchor=payload.end_anchor)
    except LookupError as e:
        raise HTTPException(404, str(e))
    return ReadingSessionOut.from_orm(rs)


@app.get("/api/reading/sessions", response_model=List[ReadingSessionOut])
def list_reading_sessions(
    book_id: int,
    include_archived: bool = False,
    limit: int = 50,
):
    lib = get_library()
    svc = ReadingSessionService(lib.session)
    rows = svc.list_for_book(book_id, include_archived=include_archived, limit=limit)
    return [ReadingSessionOut.from_orm(r) for r in rows]


@app.delete("/api/reading/sessions/{uuid}", status_code=204)
def delete_reading_session(uuid: str, hard: bool = False):
    lib = get_library()
    svc = ReadingSessionService(lib.session)
    rs = svc.get_by_uuid(uuid)
    if rs is None:
        raise HTTPException(404, f"ReadingSession {uuid} not found")
    if hard:
        svc.hard_delete(rs)
    else:
        svc.archive(rs)
    return None


@app.post("/api/reading/sessions/{uuid}/restore", response_model=ReadingSessionOut)
def restore_reading_session(uuid: str):
    lib = get_library()
    svc = ReadingSessionService(lib.session)
    rs = svc.get_by_uuid(uuid)
    if rs is None:
        raise HTTPException(404, f"ReadingSession {uuid} not found")
    svc.restore(rs)
    return ReadingSessionOut.from_orm(rs)
```

Add progress endpoints:

```python
def _get_or_create_personal(session, book_id: int) -> PersonalMetadata:
    pm = session.query(PersonalMetadata).filter_by(book_id=book_id).first()
    if pm is None:
        pm = PersonalMetadata(book_id=book_id)
        session.add(pm)
        session.flush()
    return pm


@app.get("/api/reading/progress", response_model=ProgressOut)
def get_reading_progress(book_id: int):
    lib = get_library()
    pm = lib.session.query(PersonalMetadata).filter_by(book_id=book_id).first()
    if pm is None:
        return ProgressOut(book_id=book_id, anchor=None, percentage=None, updated_at=None)
    return ProgressOut(
        book_id=book_id,
        anchor=pm.progress_anchor,
        percentage=float(pm.reading_progress) if pm.reading_progress is not None else None,
        updated_at=pm.date_added.isoformat() if pm.date_added else None,
    )


@app.post("/api/reading/progress", response_model=ProgressOut)
def post_reading_progress(payload: ProgressIn):
    """Auto-sync endpoint: accept only if new percentage is at or after current."""
    lib = get_library()
    pm = _get_or_create_personal(lib.session, payload.book_id)
    current_pct = pm.reading_progress or 0
    if payload.percentage is not None and payload.percentage < current_pct:
        raise HTTPException(409, (
            f"Progress would go backwards: current={current_pct}, "
            f"new={payload.percentage}. Use PATCH to force-set."
        ))
    pm.progress_anchor = payload.anchor
    if payload.percentage is not None:
        pm.reading_progress = int(round(payload.percentage))
    lib.session.commit()
    return ProgressOut(
        book_id=payload.book_id,
        anchor=pm.progress_anchor,
        percentage=float(pm.reading_progress) if pm.reading_progress is not None else None,
        updated_at=None,
    )


@app.patch("/api/reading/progress", response_model=ProgressOut)
def patch_reading_progress(payload: ProgressIn):
    """Explicit-set endpoint: always wins, bypasses the forward-only check."""
    lib = get_library()
    pm = _get_or_create_personal(lib.session, payload.book_id)
    pm.progress_anchor = payload.anchor
    if payload.percentage is not None:
        pm.reading_progress = int(round(payload.percentage))
    lib.session.commit()
    return ProgressOut(
        book_id=payload.book_id,
        anchor=pm.progress_anchor,
        percentage=float(pm.reading_progress) if pm.reading_progress is not None else None,
        updated_at=None,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/test_server_reading.py -q
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:
```bash
git add book_memex/server.py tests/test_server_reading.py
git commit -m "$(cat <<'EOF'
feat(api): add /api/reading/sessions and /api/reading/progress endpoints

Sessions:
  POST /api/reading/sessions/start
  POST /api/reading/sessions/{uuid}/end (idempotent)
  GET /api/reading/sessions?book_id=...
  DELETE /api/reading/sessions/{uuid}?hard={false|true}
  POST /api/reading/sessions/{uuid}/restore

Progress (on PersonalMetadata):
  GET /api/reading/progress?book_id=...
  POST /api/reading/progress (auto-sync; rejects backward moves)
  PATCH /api/reading/progress (explicit set; always wins)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Reading state MCP tools

**Files:**
- Modify: `book_memex/mcp/tools.py`
- Modify: `book_memex/mcp/server.py`
- Create: `tests/test_mcp_reading_tools.py`

Mirror the REST reading-session and progress endpoints as MCP tools.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_reading_tools.py`:

```python
"""Tests for MCP reading-state tool implementations."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.mcp.tools import (
    start_reading_session_impl, end_reading_session_impl,
    list_reading_sessions_impl, delete_reading_session_impl,
    restore_reading_session_impl,
    get_reading_progress_impl, set_reading_progress_impl,
)


@pytest.fixture
def lib_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    yield lib, book
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_start_and_end_session(lib_and_book):
    lib, book = lib_and_book
    started = start_reading_session_impl(
        lib.session, book_id=book.id, start_anchor={"cfi": "X"}
    )
    assert started["uri"].startswith("book-memex://reading/")
    ended = end_reading_session_impl(
        lib.session, uuid=started["uuid"], end_anchor={"cfi": "Y"}
    )
    assert ended["end_time"] is not None


def test_list_reading_sessions(lib_and_book):
    lib, book = lib_and_book
    start_reading_session_impl(lib.session, book_id=book.id)
    start_reading_session_impl(lib.session, book_id=book.id)
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert len(rows) == 2


def test_soft_delete_and_restore_session(lib_and_book):
    lib, book = lib_and_book
    s = start_reading_session_impl(lib.session, book_id=book.id)
    delete_reading_session_impl(lib.session, uuid=s["uuid"])
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert s["uuid"] not in {r["uuid"] for r in rows}
    restore_reading_session_impl(lib.session, uuid=s["uuid"])
    rows = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert s["uuid"] in {r["uuid"] for r in rows}


def test_progress_get_and_set(lib_and_book):
    lib, book = lib_and_book
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["anchor"] is None

    set_reading_progress_impl(
        lib.session, book_id=book.id,
        anchor={"cfi": "Z"}, percentage=30, force=False,
    )
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["anchor"] == {"cfi": "Z"}
    assert p["percentage"] == 30


def test_progress_rejects_backward(lib_and_book):
    lib, book = lib_and_book
    set_reading_progress_impl(
        lib.session, book_id=book.id, anchor={"cfi": "A"}, percentage=50, force=False
    )
    with pytest.raises(ValueError):
        set_reading_progress_impl(
            lib.session, book_id=book.id, anchor={"cfi": "B"}, percentage=20, force=False
        )

    # force=True bypasses the check.
    set_reading_progress_impl(
        lib.session, book_id=book.id, anchor={"cfi": "B"}, percentage=20, force=True
    )
    p = get_reading_progress_impl(lib.session, book_id=book.id)
    assert p["percentage"] == 20
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/test_mcp_reading_tools.py -q
```
Expected: import errors on the missing `*_impl` functions.

- [ ] **Step 3: Implement the tool functions**

Add to `book_memex/mcp/tools.py`:

```python
from book_memex.services.reading_session_service import ReadingSessionService
from book_memex.db.models import ReadingSession, PersonalMetadata


def _reading_session_to_dict(rs: ReadingSession) -> Dict[str, Any]:
    return {
        "uuid": rs.uuid,
        "uri": rs.uri,
        "book_id": rs.book_id,
        "start_time": rs.start_time.isoformat(),
        "end_time": rs.end_time.isoformat() if rs.end_time else None,
        "start_anchor": rs.start_anchor,
        "end_anchor": rs.end_anchor,
        "pages_read": rs.pages_read,
        "archived_at": rs.archived_at.isoformat() if rs.archived_at else None,
    }


def start_reading_session_impl(
    session: Session, *, book_id: int,
    start_anchor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    svc = ReadingSessionService(session)
    rs = svc.start(book_id=book_id, start_anchor=start_anchor)
    return _reading_session_to_dict(rs)


def end_reading_session_impl(
    session: Session, *, uuid: str,
    end_anchor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    svc = ReadingSessionService(session)
    rs = svc.end(uuid, end_anchor=end_anchor)
    return _reading_session_to_dict(rs)


def list_reading_sessions_impl(
    session: Session, *, book_id: int,
    include_archived: bool = False, limit: int = 50,
) -> List[Dict[str, Any]]:
    svc = ReadingSessionService(session)
    rows = svc.list_for_book(book_id, include_archived=include_archived, limit=limit)
    return [_reading_session_to_dict(r) for r in rows]


def delete_reading_session_impl(
    session: Session, *, uuid: str, hard: bool = False,
) -> Dict[str, Any]:
    svc = ReadingSessionService(session)
    rs = svc.get_by_uuid(uuid)
    if rs is None:
        raise LookupError(f"ReadingSession {uuid} not found")
    if hard:
        svc.hard_delete(rs)
    else:
        svc.archive(rs)
    return {"status": "ok", "uuid": uuid, "hard": hard}


def restore_reading_session_impl(session: Session, *, uuid: str) -> Dict[str, Any]:
    svc = ReadingSessionService(session)
    rs = svc.get_by_uuid(uuid)
    if rs is None:
        raise LookupError(f"ReadingSession {uuid} not found")
    svc.restore(rs)
    return _reading_session_to_dict(rs)


def get_reading_progress_impl(session: Session, *, book_id: int) -> Dict[str, Any]:
    pm = session.query(PersonalMetadata).filter_by(book_id=book_id).first()
    if pm is None:
        return {"book_id": book_id, "anchor": None, "percentage": None}
    return {
        "book_id": book_id,
        "anchor": pm.progress_anchor,
        "percentage": float(pm.reading_progress) if pm.reading_progress is not None else None,
    }


def set_reading_progress_impl(
    session: Session, *, book_id: int,
    anchor: Dict[str, Any], percentage: Optional[float] = None,
    force: bool = False,
) -> Dict[str, Any]:
    pm = session.query(PersonalMetadata).filter_by(book_id=book_id).first()
    if pm is None:
        pm = PersonalMetadata(book_id=book_id)
        session.add(pm)
        session.flush()
    current_pct = pm.reading_progress or 0
    if (not force) and percentage is not None and percentage < current_pct:
        raise ValueError(
            f"Progress would go backwards: current={current_pct}, new={percentage}. "
            f"Pass force=True to override."
        )
    pm.progress_anchor = anchor
    if percentage is not None:
        pm.reading_progress = int(round(percentage))
    session.commit()
    return {
        "book_id": book_id,
        "anchor": pm.progress_anchor,
        "percentage": float(pm.reading_progress) if pm.reading_progress is not None else None,
    }
```

- [ ] **Step 4: Register the tools in the MCP server**

In `book_memex/mcp/server.py`, inside `create_mcp_server`, after the marginalia tools, add:

```python
    from book_memex.mcp.tools import (
        start_reading_session_impl, end_reading_session_impl,
        list_reading_sessions_impl, delete_reading_session_impl,
        restore_reading_session_impl,
        get_reading_progress_impl, set_reading_progress_impl,
    )

    @mcp.tool(
        name="start_reading_session",
        description="Start a reading session for a book. Optional start_anchor (CFI or page).",
    )
    def start_reading_session(book_id: int, start_anchor: dict | None = None) -> dict:
        return start_reading_session_impl(
            library.session, book_id=book_id, start_anchor=start_anchor,
        )

    @mcp.tool(
        name="end_reading_session",
        description="End a reading session by uuid. Idempotent: ending an already-ended session returns it unchanged.",
    )
    def end_reading_session(uuid: str, end_anchor: dict | None = None) -> dict:
        return end_reading_session_impl(
            library.session, uuid=uuid, end_anchor=end_anchor,
        )

    @mcp.tool(
        name="list_reading_sessions",
        description="List reading sessions for a book.",
    )
    def list_reading_sessions(
        book_id: int, include_archived: bool = False, limit: int = 50,
    ) -> list:
        return list_reading_sessions_impl(
            library.session, book_id=book_id,
            include_archived=include_archived, limit=limit,
        )

    @mcp.tool(
        name="delete_reading_session",
        description="Soft-delete (archive) or hard-delete a reading session.",
    )
    def delete_reading_session(uuid: str, hard: bool = False) -> dict:
        return delete_reading_session_impl(library.session, uuid=uuid, hard=hard)

    @mcp.tool(
        name="restore_reading_session",
        description="Restore a soft-deleted reading session.",
    )
    def restore_reading_session(uuid: str) -> dict:
        return restore_reading_session_impl(library.session, uuid=uuid)

    @mcp.tool(
        name="get_reading_progress",
        description="Get the current reading progress (anchor + percentage) for a book.",
    )
    def get_reading_progress(book_id: int) -> dict:
        return get_reading_progress_impl(library.session, book_id=book_id)

    @mcp.tool(
        name="set_reading_progress",
        description="Set reading progress for a book. Rejects backward progress unless force=True.",
    )
    def set_reading_progress(
        book_id: int, anchor: dict,
        percentage: float | None = None, force: bool = False,
    ) -> dict:
        return set_reading_progress_impl(
            library.session, book_id=book_id, anchor=anchor,
            percentage=percentage, force=force,
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_mcp_reading_tools.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/mcp/tools.py book_memex/mcp/server.py tests/test_mcp_reading_tools.py
git commit -m "$(cat <<'EOF'
feat(mcp): add reading-session and reading-progress tools

Seven new tools: start_reading_session, end_reading_session,
list_reading_sessions, delete_reading_session, restore_reading_session,
get_reading_progress, set_reading_progress.

set_reading_progress rejects backward progress unless force=True,
matching the REST POST/PATCH split.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Extend arkiv export with new record kinds

**Files:**
- Modify: `book_memex/exports/arkiv.py` (or wherever ebk's arkiv exporter lives)
- Modify: `tests/test_exports.py` (add cases)

Extend the arkiv exporter so that Marginalia and ReadingSession records are emitted as JSONL with their URIs. schema.yaml gets matching entries.

- [ ] **Step 1: Locate the existing arkiv exporter**

Run:
```bash
grep -rn "arkiv" book_memex/ | grep -v __pycache__ | head -20
```

Note the path of the exporter (likely `book_memex/exports/arkiv.py` or `book_memex/services/export_service.py`). Open it and identify:
- The function or class that writes JSONL records per entity.
- The function that writes `schema.yaml`.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_exports.py` (or create a new `tests/test_arkiv_export.py` if clearer):

```python
import json
import tempfile
import shutil
from pathlib import Path

import pytest
import yaml

from book_memex.library_db import Library
from book_memex.services.marginalia_service import MarginaliaService
from book_memex.services.reading_session_service import ReadingSessionService


@pytest.fixture
def lib_with_data():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    m_svc = MarginaliaService(lib.session)
    r_svc = ReadingSessionService(lib.session)
    m = m_svc.create(
        content="note", highlighted_text="p",
        book_ids=[book.id], page_number=3, color="#ffff00",
    )
    rs = r_svc.start(book_id=book.id, start_anchor={"cfi": "X"})
    r_svc.end(rs.uuid, end_anchor={"cfi": "Y"})
    yield lib, book, m, rs
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_arkiv_export_includes_marginalia_and_reading(lib_with_data):
    lib, book, m, rs = lib_with_data
    out = Path(tempfile.mkdtemp())
    try:
        lib.export_arkiv(out)  # or: ArkivExporter(lib).run(out)  — match actual signature
        records_path = out / "records.jsonl"
        schema_path = out / "schema.yaml"
        assert records_path.exists()
        assert schema_path.exists()

        with open(records_path) as f:
            records = [json.loads(line) for line in f if line.strip()]
        kinds = {r.get("kind") for r in records}
        assert "book" in kinds
        assert "marginalia" in kinds
        assert "reading" in kinds

        marginalia_records = [r for r in records if r.get("kind") == "marginalia"]
        assert any(r["uri"] == m.uri for r in marginalia_records)
        assert any(r.get("color") == "#ffff00" for r in marginalia_records)

        reading_records = [r for r in records if r.get("kind") == "reading"]
        assert any(r["uri"] == rs.uri for r in reading_records)

        with open(schema_path) as f:
            schema = yaml.safe_load(f)
        assert "marginalia" in schema.get("kinds", {})
        assert "reading" in schema.get("kinds", {})
    finally:
        shutil.rmtree(out, ignore_errors=True)
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
pytest tests/test_exports.py -q -k arkiv
```
Expected: the new kinds are missing from the export.

- [ ] **Step 4: Implement the extension**

In the arkiv exporter:

1. Add a step that iterates all Marginalia rows, emitting one JSONL line per row:
   ```python
   for m in session.query(Marginalia).filter(Marginalia.archived_at.is_(None)).all():
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
           "created_at": m.created_at.isoformat(),
           "updated_at": m.updated_at.isoformat() if m.updated_at else None,
       }
   ```
2. Add a step for ReadingSession:
   ```python
   for rs in session.query(ReadingSession).filter(ReadingSession.archived_at.is_(None)).all():
       yield {
           "kind": "reading",
           "uri": rs.uri,
           "uuid": rs.uuid,
           "book_uri": rs.book.uri,
           "start_time": rs.start_time.isoformat(),
           "end_time": rs.end_time.isoformat() if rs.end_time else None,
           "start_anchor": rs.start_anchor,
           "end_anchor": rs.end_anchor,
           "pages_read": rs.pages_read,
       }
   ```
3. Update `schema.yaml` generation to include the new kinds, with their field descriptions.

(Adjust the code to match the exporter's existing structure; if it uses class-based exporters, add `_export_marginalia()` and `_export_reading_sessions()` methods and call them from the main export method.)

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/test_exports.py -q -k arkiv
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add book_memex/exports/arkiv.py tests/test_exports.py
git commit -m "$(cat <<'EOF'
feat(exports): arkiv export includes marginalia and reading sessions

Each record has its URI (book-memex://marginalia/... and
book-memex://reading/...) and links to books by URI. schema.yaml
gains `marginalia` and `reading` kind entries.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: End-to-end integration test

**Files:**
- Create: `tests/test_phase1_e2e.py`

Round-trip test exercising REST + MCP paths: import a book, create marginalia via REST, fetch via MCP, soft-delete, verify hidden from default listings, restore, verify visible, hard-delete, verify gone. Also exercises session start/end and progress get/set.

- [ ] **Step 1: Write the test**

Create `tests/test_phase1_e2e.py`:

```python
"""End-to-end Phase 1 integration test."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library
from book_memex.mcp.tools import (
    list_marginalia_impl, get_marginalia_impl,
    list_reading_sessions_impl, get_reading_progress_impl,
)
from book_memex.core.uri import parse_uri


@pytest.fixture
def e2e_env():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "book.txt"; p.write_text("hello world")
    book = lib.add_book(
        p, metadata={"title": "Test Book", "creators": ["Author"]},
        extract_text=False,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_marginalia_roundtrip_rest_and_mcp(e2e_env):
    client, book, lib = e2e_env

    # Create via REST
    r = client.post("/api/marginalia", json={
        "book_ids": [book.id],
        "content": "note",
        "highlighted_text": "world",
        "page_number": 1,
        "color": "#ffff00",
    })
    assert r.status_code == 201
    uuid = r.json()["uuid"]
    uri = r.json()["uri"]

    # URI parses correctly
    parsed = parse_uri(uri)
    assert parsed.kind == "marginalia"
    assert parsed.id == uuid

    # Fetchable via MCP
    via_mcp = get_marginalia_impl(lib.session, uuid=uuid)
    assert via_mcp["uri"] == uri
    assert via_mcp["scope"] == "highlight"

    # Soft-delete via REST
    r = client.delete(f"/api/marginalia/{uuid}")
    assert r.status_code == 204

    # Hidden from default MCP list
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid not in {m["uuid"] for m in rows}

    # Visible with include_archived
    rows = list_marginalia_impl(
        lib.session, book_id=book.id, include_archived=True
    )
    assert uuid in {m["uuid"] for m in rows}

    # Restore via REST
    r = client.post(f"/api/marginalia/{uuid}/restore")
    assert r.status_code == 200

    # Visible again
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid in {m["uuid"] for m in rows}

    # Hard-delete via REST
    r = client.delete(f"/api/marginalia/{uuid}?hard=true")
    assert r.status_code == 204

    # Gone from MCP
    import pytest as _pt
    with _pt.raises(LookupError):
        get_marginalia_impl(lib.session, uuid=uuid)


def test_reading_session_and_progress_roundtrip(e2e_env):
    client, book, lib = e2e_env

    # Start session via REST
    r = client.post("/api/reading/sessions/start", json={
        "book_id": book.id,
        "start_anchor": {"cfi": "epubcfi(/6/4!/4)"},
    })
    assert r.status_code == 201
    rs_uuid = r.json()["uuid"]

    # Post progress via REST
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "epubcfi(/6/4!/6)"},
        "percentage": 30,
    })
    assert r.status_code == 200

    # Fetchable via MCP
    sessions = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert rs_uuid in {s["uuid"] for s in sessions}

    prog = get_reading_progress_impl(lib.session, book_id=book.id)
    assert prog["anchor"] == {"cfi": "epubcfi(/6/4!/6)"}
    assert prog["percentage"] == 30

    # End session via REST
    r = client.post(f"/api/reading/sessions/{rs_uuid}/end", json={
        "end_anchor": {"cfi": "epubcfi(/6/4!/8)"},
    })
    assert r.status_code == 200
    assert r.json()["end_time"] is not None

    # Session is now complete in MCP
    s = next(s for s in list_reading_sessions_impl(lib.session, book_id=book.id)
             if s["uuid"] == rs_uuid)
    assert s["end_time"] is not None
    assert s["end_anchor"] == {"cfi": "epubcfi(/6/4!/8)"}
```

- [ ] **Step 2: Run the test**

Run:
```bash
pytest tests/test_phase1_e2e.py -q
```
Expected: all tests pass.

- [ ] **Step 3: Run the full test suite with coverage**

Run:
```bash
pytest --cov=book_memex --cov-report=term-missing
```
Expected: all tests pass. Coverage on new modules (`book_memex/core/uri.py`, `book_memex/core/soft_delete.py`, `book_memex/services/reading_session_service.py`, extended marginalia service) is 90%+.

- [ ] **Step 4: Commit**

Run:
```bash
git add tests/test_phase1_e2e.py
git commit -m "$(cat <<'EOF'
test: add phase-1 end-to-end integration tests

Covers the full marginalia lifecycle (REST create -> MCP read ->
REST soft-delete -> restore -> hard-delete) and the reading-state
roundtrip (start session, post progress, end session; all via REST,
verified via MCP).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (for plan authors)

After implementing all tasks above, an engineer should be able to:

1. Install the renamed package (`pip install -e ".[dev]"`) and invoke `book-memex --help` and `ebk --help` (with deprecation notice).
2. Start the FastAPI server (`book-memex serve`) and exercise `/api/marginalia`, `/api/reading/sessions`, `/api/reading/progress` via `curl` or a test client.
3. Start the MCP server (`book-memex mcp-serve`) and exercise the 13 new tools (6 marginalia, 5 session, 2 progress) via an MCP client.
4. Observe URIs on every marginalia and reading-session record (`book-memex://marginalia/<uuid>`, `book-memex://reading/<uuid>`).
5. Soft-delete any marginalia/reading-session, verify it is hidden from default listings, restore it, and hard-delete it.
6. Export a library with arkiv and see Marginalia + ReadingSession JSONL lines with URIs.

Phase 1 intentionally does NOT include: content extraction evolution (Phase 2), content-level FTS5 search (Phase 2), `ask_book` (Phase 2), browser reader UI (Phase 3).

## Notes for the executing agent

- Every task has an explicit commit; do not batch commits across tasks.
- If a test fails mid-task, diagnose and fix the failing test or implementation before proceeding. Do not skip steps.
- The `server.py` is 3600+ lines. Preserve its existing routing style when inserting new endpoints. If that style uses an `APIRouter` rather than `@app.<method>`, adapt the code in Task 8 and Task 11 accordingly; the endpoint paths and Pydantic models stay the same.
- The `ebk` CLI alias and its deprecation shim (Task 1) are scheduled for removal in the release after v1. Do not remove them in this plan.
- If any test relies on a fixture that does not yet exist in `tests/conftest.py`, add it there rather than inside the test file, matching ebk's existing convention of root-level fixtures.
